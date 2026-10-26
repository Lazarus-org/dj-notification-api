from typing import Any

from rest_framework.serializers import ModelSerializer, SerializerMethodField

from django_notification.constants.default_settings import default_serializer_settings
from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.utils.serialization import (
    filter_non_empty_fields,
    generate_title,
)


class NotificationDynamicSerializer(ModelSerializer):
    """Serializer for Notification model that dynamically selects fields based on
    settings or predefined fields.

    The normal API path accepts Notification instances. Dictionaries supplied
    by legacy integrations are also supported for backward compatibility.

    Fields to be serialized are determined by `config.notification_serializer_fields`
    if set, otherwise defaults to a predefined set of fields including 'id', 'title',
    'status', 'link', and 'timestamp'.

    Attributes:
        title (SerializerMethodField): Field for serializing the title, dynamically
            determined based on configuration.

    Meta:
        model (Notification): Django model associated with this serializer.
        fields (tuple): Fields to be serialized, either fetched from
            `config.notification_serializer_fields` or a predefined list.

    """

    title = (
        SerializerMethodField()
        if not config.notification_serializer_fields
        or "title" in config.notification_serializer_fields
        else None
    )

    class Meta:
        model = Notification
        fields = config.notification_serializer_fields or [
            "title",
            *default_serializer_settings.notification_serializer_fields,
        ]

    def get_title(self, notification: Notification | dict[str, Any]) -> str:
        """Render the same title from model objects or legacy dictionaries.

        Model instances are the native API path. For a legacy dict, retain its
        historical title generation, including configured- field behavior.

        """
        if isinstance(notification, Notification):
            return str(notification)
        if config.notification_serializer_fields:
            return str(notification)
        return generate_title(notification)

    def to_representation(
        self, instance: Notification | dict[str, Any]
    ) -> dict[str, Any]:
        """Serialize models and historical dictionaries, omitting nulls if set."""
        data = super().to_representation(instance)

        if config.exclude_serializer_null_fields:
            return filter_non_empty_fields(data)

        return data
