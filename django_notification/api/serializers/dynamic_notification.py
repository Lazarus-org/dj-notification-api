from typing import Any, Dict, Union

from rest_framework.serializers import ModelSerializer, SerializerMethodField

from django_notification.constants.default_settings import default_serializer_settings
from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.utils.serialization import (
    filter_non_empty_fields,
    generate_title,
)


class NotificationDynamicSerializer(ModelSerializer):
    """Serializer for Notification model that dynamically selects fields based
    on settings or predefined fields.

    If `config.notification_serializer_fields` is defined and includes 'title',
    the 'title' field will be serialized using a SerializerMethodField. Otherwise,
    'title' will default to a SerializerMethodField.

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

    def get_title(self, notification: Union[Notification, Dict[str, Any]]) -> str:
        """Generate and return the title for a notification.

        Args:
            notification (Union[Notification, Dict[str, Any]]): The notification instance or its dictionary representation.

        Returns:
            str: The dynamically generated title.

        """
        return (
            str(notification)
            if config.notification_serializer_fields
            else generate_title(notification)
        )

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, str]:
        """Convert the instance to a representation format, filtering out empty
        fields.

        Args:
            instance (Dict[str, Any]): A dictionary representing the notification data,
                typically from a queryset's values().

        Returns:
            Dict[str, str]: The filtered representation of the notification data.

        """
        data = super().to_representation(instance)

        if config.exclude_serializer_null_fields:
            return filter_non_empty_fields(data)

        return data
