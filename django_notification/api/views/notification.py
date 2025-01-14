from typing import List, Type

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from django_notification.api.serializers.notification import NotificationSerializer
from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.mixins import ConfigurableAttrsMixin, DisableMethodsMixin
from django_notification.models.notification import Notification
from django_notification.settings.conf import config


# pylint: disable=too-many-ancestors
class NotificationViewSet(
    GenericViewSet, ListModelMixin, DisableMethodsMixin, ConfigurableAttrsMixin
):
    """API ViewSet for managing notifications.

    This viewset provides an interface for viewing and interacting with notifications.
    It allows users to list unseen notifications, mark notifications as seen, and
    retrieve detailed information about specific notifications. Depending on the
    user's role (staff or regular user), different levels of notification detail are provided.

    Features:
    - List Notifications: Retrieves a list of unseen notifications. The availability
      of this method is controlled by settings.
    - Retrieve Notification: Fetch detailed information about a specific notification
      by its ID. Mark the notification as seen upon retrieval. The availability of this
      method is controlled by settings.
    - Mark All as Seen: Marks all unseen notifications for the user as seen.

    Customizations:
    - Dynamic Serializer: Depending on the user's role or configuration settings,
      the viewset selects between `NotificationSerializer` for detailed information
      and `SimpleNotificationSerializer` for basic notification data.
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
    - Only users with proper permissions are allowed to interact with the notifications.
    - Staff users have access to more detailed views and additional features.

    Settings:
    - The availability of list and retrieve methods is determined by the configuration
      (`DJANGO_NOTIFICATION_API_ALLOW_LIST`, `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`).
    - The level of notification details returned is based on the user's role and the setting
      (`DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`).

    Parsers and filters are automatically applied based on the request's `Content-Type`
    and query parameters, making the viewset flexible and adaptable to various use cases.

    """

    filter_backends: List = [DjangoFilterBackend, OrderingFilter, SearchFilter]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the NotificationViewSet, configure dynamic attributes,
        and disable methods as needed based on settings.

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

    def get_user_groups(self) -> QuerySet:
        """Get the groups associated with the current user.

        Returns:
            QuerySet: A queryset of the groups the user belongs to.

        """
        return self.request.user.groups.all()

    def get_staff_queryset(self) -> QuerySet:
        """Get the queryset for staff users. Staff users can view all unseen
        notifications with full details.

        Returns:
            QuerySet: A queryset of unseen notifications for staff users.

        """
        return Notification.objects.unseen(
            unseen_by=self.request.user,
            display_detail=True,
        )

    def get_queryset(self, display_detail: bool = False) -> QuerySet:
        """Get the queryset of unseen notifications for the current user,
        either staff or non-staff. The queryset can include full details based
        on user roles and configuration.

        Args:
            display_detail (bool): Whether to display full details for notifications. Defaults to False.

        Returns:
            QuerySet: A queryset of unseen notifications for the current user.

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
        queryset = Notification.objects.unseen(
            unseen_by=self.request.user,
            groups=user_groups,
            display_detail=display_detail,
        )

        return queryset.distinct()

    def get_serializer_class(self) -> Type[Serializer]:
        """Get the appropriate serializer class based on the user's role and
        configuration.

        Returns:
            Type[Serializer]: The serializer class to use for the current request.

        """
        if self.request.user.is_staff or config.include_serializer_full_details:
            return NotificationSerializer

        return config.notification_serializer_class or NotificationDynamicSerializer

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve a single notification, mark it as seen, and return the
        notification data.

        Args:
            request: The current request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A Response object containing the serialized notification data.

        """
        queryset = self.filter_queryset(self.get_queryset(display_detail=True))
        notification = get_object_or_404(queryset, pk=self.kwargs["pk"])
        serializer = NotificationSerializer(notification)
        notification.mark_as_seen(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def mark_all_as_seen(self, request: Request) -> Response:
        """Mark all unseen notifications for the current user as seen.

        Args:
            request: The current request object.

        Returns:
            Response: A Response object indicating how many notifications were marked as seen.

        """
        count = Notification.objects.mark_all_as_seen(request.user)
        return Response({"detail": f"{count} Notifications marked as seen."})
