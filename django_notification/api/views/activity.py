from typing import List, Optional, Type

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.api.serializers.notification import NotificationSerializer
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
    DisableMethodsMixin,
    ConfigurableAttrsMixin,
):
    """API ViewSet for managing and interacting with user activities
    (notifications).

    This viewset allows users to view, clear, and delete their seen activities.
    The functionality provided depends on user roles and configuration settings,
    such as soft and hard deletion of notifications.

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
    - Dynamic Serializer: Based on user role and settings, the appropriate serializer
      is chosen between `NotificationSerializer` (for detailed information) and
      `SimpleNotificationSerializer` (for basic information).
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
    - The level of notification details returned is based on the user's role and the setting
      (`DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`).

    This viewset provides a flexible and configurable API for managing notification activities,
    with dynamic behavior driven by user roles and project settings.

    """

    filter_backends: List = [
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

    def get_user_groups(self) -> QuerySet:
        """Retrieve the list of groups the current user belongs to.

        Returns:
            QuerySet: A Queryset of the user's groups.

        """
        return self.request.user.groups.all()

    def get_staff_queryset(self) -> QuerySet:
        """Get the queryset for staff users. Staff users can view all seen
        notifications with full details.

        Returns:
            QuerySet: A queryset of seen notifications for staff users.

        """
        return Notification.objects.seen(seen_by=self.request.user, display_detail=True)

    def get_queryset(self, display_detail: bool = False) -> QuerySet:
        """Retrieve the queryset of seen notifications for the user.

        If the user is a staff member, all seen notifications are returned. For non-staff users,
        the level of detail returned depends on the `include_serializer_full_details` setting.

        Args:
            display_detail (bool): Whether to display full details in the queryset. Defaults to False.

        Returns:
            QuerySet: A queryset of seen notifications, filtered by user and groups.

        """
        if self.request.user.is_staff:
            return self.get_staff_queryset()

        display_detail = bool(
            display_detail
            or config.include_serializer_full_details
            or config.notification_serializer_fields
            or config.notification_serializer_class
        )

        user_groups = self.get_user_groups()
        queryset = Notification.objects.seen(
            recipients=self.request.user,
            seen_by=self.request.user,
            groups=user_groups,
            display_detail=display_detail,
        )
        return queryset.distinct()

    def get_serializer_class(self) -> Type[Serializer]:
        """Determine the appropriate serializer class based on the user's role
        and settings.

        Returns:
            Serializer: Either `NotificationSerializer` for detailed responses
            or `SimpleNotificationSerializer` for minimal responses.

        """
        if self.request.user.is_staff or config.include_serializer_full_details:
            return NotificationSerializer

        return config.notification_serializer_class or NotificationDynamicSerializer

    @conditional_action(condition=config.include_soft_delete, detail=False)
    def clear_activities(self, request: Request) -> Response:
        """Soft-delete or clear all activities for the user.

        This method is conditionally enabled based on the `include_soft_delete` setting.

        Args:
            request (Request): The current request object.

        Returns:
            Response: A response indicating that all activities have been cleared.

        """
        Notification.objects.clear_all(request.user)
        return Response(
            {"detail": "all activities cleared."}, status=status.HTTP_204_NO_CONTENT
        )

    @conditional_action(condition=config.include_soft_delete, detail=True)
    def clear_notification(
        self, request: Request, pk: Optional[str] = None
    ) -> Response:
        """Soft-delete a specific notification for the user.

        This method is conditionally enabled based on the `include_soft_delete` setting.

        Args:
            request (Request): The current request object.
            pk (Optional[str]): The primary key of the notification to be cleared.

        Returns:
            Response: A response indicating that the notification has been cleared.

        """
        Notification.objects.delete_notification(
            notification_id=pk, recipient=request.user, soft_delete=True
        )
        return Response(
            {"detail": f"notification {pk} cleared."}, status=status.HTTP_204_NO_CONTENT
        )

    @conditional_action(
        condition=config.include_hard_delete,
        permission_classes=[IsAdminUser],
        detail=False,
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
        queryset = self.filter_queryset(self.get_queryset(display_detail=True))
        queryset.delete()
        return Response(
            {"detail": "all activities deleted."}, status=status.HTTP_204_NO_CONTENT
        )

    @conditional_action(
        condition=config.include_hard_delete,
        permission_classes=[IsAdminUser],
        detail=True,
    )
    def delete_notification(
        self, request: Request, pk: Optional[str] = None
    ) -> Response:
        """Permanently delete a specific notification for the user.

        This method is conditionally enabled based on the `include_hard_delete` setting
        and restricted to admin users.

        Args:
            request (Request): The current request object.
            pk (Optional[str]): The primary key of the notification to be deleted.

        Returns:
            Response: A response indicating that the notification has been permanently deleted.

        """
        Notification.objects.delete_notification(notification_id=pk, soft_delete=False)
        return Response(
            {"detail": f"notification {pk} deleted."}, status=status.HTTP_204_NO_CONTENT
        )
