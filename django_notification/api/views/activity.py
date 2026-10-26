from django.db.models import QuerySet
from rest_framework import status
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.api.serializers.self_service_notification import (
    NotificationSelfServiceSerializer,
)
from django_notification.api.views.inbox_actions import (
    mark_legacy_get_response,
    require_mutation_method,
    validated_ids,
)
from django_notification.api.views.preferences import filter_personal_notifications
from django_notification.decorators.action import conditional_action
from django_notification.mixins import ConfigurableAttrsMixin, DisableMethodsMixin
from django_notification.models.notification import Notification
from django_notification.settings.conf import config

try:
    from django_filters.rest_framework import DjangoFilterBackend

    django_filter_installed = True
except ImportError:  # pragma: no cover
    django_filter_installed = False


# pylint: disable=too-many-ancestors
class ActivityViewSet(
    GenericViewSet,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    DisableMethodsMixin,
    ConfigurableAttrsMixin,
):
    """API ViewSet for managing and interacting with user activities (notifications).

    This viewset allows authenticated users to view and soft-delete their own
    activities addressed to them directly or through their Django groups.
    Hard deletion remains an explicitly configured admin action.

    Features:
    - List Activities: Lists all seen notifications for the user. The availability of
      this method is controlled by settings.
    - Retrieve Activity: Retrieve detailed information about a specific notification
      by its ID. The availability of this method is controlled by settings.
    - Clear Activities: Allows users to soft-delete or clear all notifications. This
      functionality is controlled by settings.
    - Delete Activities: Admin users can permanently delete notifications. This
      feature is controlled by settings.

    Customizations:
    - List Serializer: The configured serializer is selected from package settings;
      staff status does not automatically expose full details in list responses.
    - Conditional Actions: Soft and hard deletion actions are conditionally enabled
      based on settings and permissions.
      Admins have additional capabilities such as hard-deleting notifications based on settings.
    - Filtering and Searching: This view supports filtering, searching, and ordering
      of notifications via `DjangoFilterBackend`, `SearchFilter`, and `OrderingFilter`.
    - Configuration via Settings: The viewset is dynamically configured using the
      `configure_attrs` method, which adjusts method availability and functionality
      based on project settings.

    Parsers:
    - Accepts various content types, such as `application/json` and `multipart/form-data`,
      allowing flexibility in handling requests that include file uploads or JSON payloads.

    Methods:
    - `GET /activities/`: List all seen notifications.
    - `GET /activities/<id>/`: Retrieve detailed information about a specific notification.
    - `GET /activities/clear_activities/`: Soft-delete or clear all activities (conditionally enabled).
    - `GET /activities/<id>/clear_notification/`: Soft-delete a specific notification (conditionally enabled).
    - `GET /activities/delete_activities/`: Permanently delete all activities (admin only, conditionally enabled).
    - `GET /activities/<id>/delete_notification`: Permanently delete a specific notification (admin only, conditionally enabled).

    Permissions:
    - Regular Users: Can list, retrieve, and clear their own notifications.
    - Admin Users: Have additional permissions to hard-delete notifications, depending
      on the configuration.

    Settings:
    - The availability of list and retrieve methods is controlled by `DJANGO_NOTIFICATION_API_ALLOW_LIST`
      and `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE` settings.
    - The soft-delete and hard-delete functionalities are controlled by `DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE`
      and `DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE` settings.
    - List response detail level is based on
      `DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`, not staff status.

    This viewset provides a flexible and configurable API for managing notification activities,
    with behavior driven by explicit permissions and project settings.

    """

    filter_backends: list = [
        *([DjangoFilterBackend] if django_filter_installed else []),
        OrderingFilter,
        SearchFilter,
    ]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the viewset and configure attributes based on settings.

        Disables the 'list' and 'retrieve' methods if their corresponding settings
        (`api_allow_list` and `api_allow_retrieve`) are set to `False`.

        """
        super().__init__(*args, **kwargs)
        self.configure_attrs()

        # Check the setting to enable or disable the list method
        if not config.api_allow_list:
            self.disable_methods(["LIST"])

        # Check the setting to enable or disable the retrieve method
        if not config.api_allow_retrieve:
            self.disable_methods(["RETRIEVE"])

    def get_queryset(self, display_detail: bool = False) -> QuerySet:
        """Select seen activities visible to the authenticated user.

        ``display_detail`` is retained for extension compatibility, but queryset result
        types are now always model instances. Presentation belongs to the selected
        serializer.

        """
        queryset = (
            Notification.objects.visible_to(self.request.user)
            .active_at()
            .sent_only()
            .seen_by(self.request.user)
            .not_deleted_by(self.request.user)
        )
        # Built-in personal serializers do not traverse recipient/group
        # relationships. Custom serializers and explicit field projections may.
        queryset = filter_personal_notifications(queryset, self.request)
        if (
            config.notification_serializer_fields
            or config.notification_serializer_class
        ):
            return queryset.with_related()
        return queryset

    def get_serializer_class(self) -> type[Serializer]:
        """Determine the serializer class from package settings.

        Returns:
            Serializer: The serializer selected by package configuration.

        """
        if config.include_serializer_full_details:
            return NotificationSelfServiceSerializer

        return config.notification_serializer_class or NotificationDynamicSerializer

    @conditional_action(
        condition=config.include_soft_delete,
        detail=False,
        methods=["get", "post"],
    )
    def clear_activities(self, request: Request) -> Response:
        """Soft-delete or clear all activities for the user.

        This method is conditionally enabled based on the `include_soft_delete` setting.

        Args:
            request (Request): The current request object.

        Returns:
            Response: A response indicating that all activities have been cleared.

        """
        require_mutation_method(request)
        Notification.objects.clear_all(request.user)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return mark_legacy_get_response(request, response)

    @conditional_action(
        condition=config.include_soft_delete,
        detail=True,
        methods=["get", "delete"],
    )
    def clear_notification(self, request: Request, pk: str | None = None) -> Response:
        """Soft-delete a specific notification for the user.

        This method is conditionally enabled based on the `include_soft_delete` setting.

        Args:
            request (Request): The current request object.
            pk (Optional[str]): The primary key of the notification to be cleared.

        Returns:
            Response: A response indicating that the notification has been cleared.

        """
        require_mutation_method(request)
        # Individual activity mutations must satisfy the same seen-and-visible
        # queryset as the activity detail endpoint before changing state.
        activity = self.get_object()
        Notification.objects.delete_notification(
            notification_id=activity.pk, recipient=request.user, soft_delete=True
        )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return mark_legacy_get_response(request, response)

    @conditional_action(
        condition=config.include_soft_delete,
        detail=False,
        methods=["post"],
    )
    def bulk_clear(self, request: Request) -> Response:
        """Atomically clear up to 500 selected, seen activities."""
        ids = validated_ids(request)
        processed = Notification.objects.clear_selected(request.user, ids)
        return Response({"processed": processed})

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """Canonical DELETE /activities/{id}/ soft-deletes a seen activity."""
        if not config.include_soft_delete:
            raise MethodNotAllowed("DELETE")
        activity = self.get_object()
        Notification.objects.delete_notification(
            notification_id=activity.pk, recipient=request.user, soft_delete=True
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @conditional_action(
        condition=config.include_hard_delete,
        permission_classes=[IsAdminUser],
        detail=False,
        methods=["get", "delete"],
    )
    def delete_activities(self, request: Request) -> Response:
        """Permanently delete all activities for the user.

        This method is conditionally enabled based on the `include_hard_delete` setting
        and restricted to admin users.

        Args:
            request (Request): The current request object.

        Returns:
            Response: A response indicating that all activities have been permanently deleted.

        """
        require_mutation_method(request)
        queryset = self.filter_queryset(self.get_queryset(display_detail=True))
        queryset.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return mark_legacy_get_response(request, response)

    @conditional_action(
        condition=config.include_hard_delete,
        permission_classes=[IsAdminUser],
        detail=True,
        methods=["get", "delete"],
    )
    def delete_notification(self, request: Request, pk: str | None = None) -> Response:
        """Permanently delete a specific notification for the user.

        This method is conditionally enabled based on the `include_hard_delete` setting
        and restricted to admin users.

        Args:
            request (Request): The current request object.
            pk (Optional[str]): The primary key of the notification to be deleted.

        Returns:
            Response: A response indicating that the notification has been permanently deleted.

        """
        require_mutation_method(request)
        # Configured hard deletion is an admin action, but this personal
        # activity route must never accept an unrelated notification ID.
        activity = self.get_object()
        Notification.objects.delete_notification(
            notification_id=activity.pk, soft_delete=False
        )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return mark_legacy_get_response(request, response)
