from django_filters import rest_framework as filters

from django_notification.models.notification import Notification


class NotificationFilter(filters.FilterSet):
    """Filter set for filtering notifications based on various criteria."""

    timestamp = filters.DateTimeFromToRangeFilter(
        field_name="timestamp",
        lookup_expr="range",
        help_text="Filter notifications by timestamp within a specific range.",
    )

    class Meta:
        model = Notification
        fields = {
            "group__id": ["exact"],
            "recipient__id": ["exact"],
            "status": ["exact"],
            "public": ["exact"],
        }
