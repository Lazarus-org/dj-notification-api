"""Privacy-safe full notification representation for personal API endpoints."""

from rest_framework.serializers import ModelSerializer, SerializerMethodField

from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.utils.serialization.field_filters import (
    filter_non_empty_fields,
)


class NotificationSelfServiceSerializer(ModelSerializer):
    """Render notification content without unrelated recipients' identities.

    The administrative NotificationSerializer remains available to trusted integrations,
    but it must not be used for personal notification feeds. Arbitrary application
    metadata is excluded from the default public contract.

    """

    title = SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "title",
            "verb",
            "description",
            "status",
            "link",
            "is_sent",
            "public",
            "category",
            "priority",
            "timestamp",
        )

    def get_title(self, notification: Notification) -> str:
        """Return the established human-readable notification title."""
        return str(notification)

    def to_representation(self, instance: Notification) -> dict:
        """Preserve the configured suppression of empty response fields."""
        data = super().to_representation(instance)
        if config.exclude_serializer_null_fields:
            return filter_non_empty_fields(data)
        return data
