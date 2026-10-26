from django.db.models import Count, Exists, OuterRef, QuerySet
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import ListModelMixin
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
from django_notification.api.views.delivery_schedule import (
    NotificationDeliveryScheduleActionsMixin,
)
from django_notification.api.views.inbox_actions import (
    mark_legacy_get_response,
    require_mutation_method,
    validated_ids,
)
from django_notification.api.views.preferences import (
    NotificationChannelPreferenceActionsMixin,
    NotificationPreferenceActionsMixin,
    filter_personal_notifications,
)
from django_notification.mixins import ConfigurableAttrsMixin, DisableMethodsMixin
from django_notification.models.notification import Notification
from django_notification.models.notification_seen import NotificationSeen
from django_notification.settings.conf import config

try:
    from django_filters.rest_framework import DjangoFilterBackend

    django_filter_installed = True
except ImportError:  # pragma: no cover
    django_filter_installed = False


# pylint: disable=too-many-ancestors
class NotificationViewSet(
    NotificationDeliveryScheduleActionsMixin,
    NotificationPreferenceActionsMixin,
    NotificationChannelPreferenceActionsMixin,
    GenericViewSet,
    ListModelMixin,
    DisableMethodsMixin,
    ConfigurableAttrsMixin,
):
    """API ViewSet for managing notifications.

    This viewset provides an interface for viewing and interacting with notifications.
    It allows authenticated users to list unseen notifications, mark notifications as
    seen, and retrieve notifications addressed to them individually or through their
    current Django groups. Staff status alone does not widen this scope.

    Features:
    - List Notifications: Retrieves a list of unseen notifications. The availability
      of this method is controlled by settings.
    - Retrieve Notification: Fetch detailed information about a specific notification
      by its ID. Mark the notification as seen upon retrieval. The availability of this
      method is controlled by settings.
    - Mark All as Seen: Marks all unseen notifications for the user as seen.

    Customizations:
    - List Serializer: The configured serializer is selected from package settings;
      staff status does not automatically expose full details in list responses.
    - Filtering and Searching: Supports filtering, searching, and ordering through
      Django filters (`DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`).
    - Configuration via Settings: Additional functionality and attributes, such as
      method availability and serializer details, are configured through project settings
      and dynamically applied in the `configure_attrs` method.

    Parsers:
    - Accepts various content types, such as `application/json` and `multipart/form-data`,
      allowing flexibility in handling requests that include file uploads or JSON payloads.

    Methods:
    - `GET /notifications/`: List unseen notifications.
    - `GET /notifications/<id>/`: Retrieve detailed information about a specific notification.
    - `GET /notifications/mark_all_as_seen/`: Mark all unseen notifications as seen.

    Permissions:
    - Read-state actions require direct recipient or targeted-group membership.
    - Staff status alone does not grant access to another user's notifications.

    Settings:
    - The availability of list and retrieve methods is determined by the configuration
      (`DJANGO_NOTIFICATION_API_ALLOW_LIST`, `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`).
    - List response detail level is based on
      `DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`, not the user's role.

    Parsers and filters are automatically applied based on the request's `Content-Type`
    and query parameters, making the viewset flexible and adaptable to various use cases.

    """

    filter_backends: list = [
        *([DjangoFilterBackend] if django_filter_installed else []),
        OrderingFilter,
        SearchFilter,
    ]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the NotificationViewSet, configure dynamic attributes, and disable
        methods as needed based on settings.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

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
        """Select unseen notifications visible to the authenticated user.

        ``display_detail`` is retained for extension compatibility, but queryset result
        types are now always model instances. Presentation belongs to the selected
        serializer.

        """
        queryset = (
            Notification.objects.visible_to(self.request.user)
            .active_at()
            .sent_only()
            .unseen_by(self.request.user)
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
        """Get the appropriate serializer class based on package configuration.

        Returns:
            Type[Serializer]: The serializer class to use for the current request.

        """
        if config.include_serializer_full_details:
            return NotificationSelfServiceSerializer

        return config.notification_serializer_class or NotificationDynamicSerializer

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve personal notification details using the configured legacy automatic
        mark-seen policy.

        Args:
            request: The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A Response object containing the serialized notification data.

        """
        queryset = self.filter_queryset(self.get_queryset(display_detail=True))
        notification = get_object_or_404(queryset, pk=self.kwargs["pk"])
        serializer = NotificationSelfServiceSerializer(notification)
        if config.api_retrieve_marks_seen and config.api_allow_legacy_get_mutations:
            notification.mark_as_seen(request.user)
            return mark_legacy_get_response(request, Response(serializer.data))
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def summary(self, request: Request) -> Response:
        """Return undeleted, sent, visible total/read/unread counts."""
        if not config.api_allow_list:
            raise MethodNotAllowed("GET")
        user = request.user
        queryset = (
            Notification.objects.visible_to(user)
            .active_at()
            .sent_only()
            .not_deleted_by(user)
        )
        seen = NotificationSeen.objects.filter(
            notification_id=OuterRef("pk"), user_id=user.pk
        )
        queryset = filter_personal_notifications(queryset, request)
        counts = queryset.aggregate(
            total_count=Count("pk"),
            read_count=Count("pk", filter=Exists(seen)),
        )
        return Response(
            {
                "total_count": counts["total_count"],
                "read_count": counts["read_count"],
                "unread_count": counts["total_count"] - counts["read_count"],
            }
        )

    @action(detail=True, methods=["get"])
    def preview(self, request: Request, pk: str = "") -> Response:
        """Read a visible notification without changing its read state."""
        if not config.api_allow_retrieve:
            raise MethodNotAllowed("GET")
        queryset = (
            Notification.objects.visible_to(request.user)
            .active_at()
            .sent_only()
            .not_deleted_by(request.user)
        )
        notification = get_object_or_404(queryset, pk=pk)
        return Response(NotificationSelfServiceSerializer(notification).data)

    @action(detail=True, methods=["post"])
    def mark_seen(self, request: Request, pk: str = "") -> Response:
        """Idempotently mark one directly or group-addressed notification read."""
        changed = Notification.objects.set_seen(request.user, pk, seen=True)
        return Response({"id": int(pk), "seen": True, "changed": changed})

    @action(detail=True, methods=["post"])
    def mark_unseen(self, request: Request, pk: str = "") -> Response:
        """Idempotently mark one visible notification unread."""
        changed = Notification.objects.set_seen(request.user, pk, seen=False)
        return Response({"id": int(pk), "seen": False, "changed": changed})

    @action(detail=False, methods=["post"])
    def bulk_mark_seen(self, request: Request) -> Response:
        """Mark up to 500 explicitly selected visible notifications read."""
        ids = validated_ids(request)
        processed = Notification.objects.set_many_seen(request.user, ids, seen=True)
        return Response({"processed": processed, "seen": True})

    @action(detail=False, methods=["post"])
    def bulk_mark_unseen(self, request: Request) -> Response:
        """Mark up to 500 explicitly selected visible notifications unread."""
        ids = validated_ids(request)
        processed = Notification.objects.set_many_seen(request.user, ids, seen=False)
        return Response({"processed": processed, "seen": False})

    @action(detail=False, methods=["get", "post"])
    def mark_all_as_seen(self, request: Request) -> Response:
        """Mark all unseen notifications for the current user as seen.

        Args:
            request: The current request object.

        Returns:
            Response: A Response object indicating how many notifications were marked as seen.

        """
        require_mutation_method(request)
        count = Notification.objects.mark_all_as_seen(request.user)
        response = Response({"detail": f"{count} Notifications marked as seen."})
        return mark_legacy_get_response(request, response)
