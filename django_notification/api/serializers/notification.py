from typing import Dict, Type

from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    BaseSerializer,
)
from django_notification.api.serializers import GroupSerializer, UserSerializer
from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.utils.serialization.field_filters import (
    filter_non_empty_fields,
)


class NotificationSerializer(ModelSerializer):
    """
    Serializer for the Notification model, including related Group and User data.

    Fields:
        id: Unique identifier for the notification.
        title: Computed title of the notification.
        recipient: User(s) who are the recipients of the notification.
        group: Group(s) associated with the notification.
        verb: Action performed (e.g., "created", "updated").
        status: Current status of the notification.
        actor_content_type: Type of actor associated with the notification.
        target_content_type: Type of target associated with the notification.
        action_object_content_type: Type of action object associated with the notification.
        link: URL link related to the notification.
        is_sent: Indicates whether the notification has been sent.
        seen_by: User(s) who have seen the notification.
        public: Boolean indicating if the notification is public.
        data: Additional data associated with the notification.
        timestamp: Time when the notification was created.
    """

    @staticmethod
    def group_serializer_class():
        """
        Get the serializer class for the group field, either from config or the default.
        """
        return config.group_serializer_class or GroupSerializer

    @staticmethod
    def user_serializer_class() -> Type[BaseSerializer]:
        """
        Get the serializer class for the recipient and seen_by fields, either from config or the default.
        """
        return config.user_serializer_class or UserSerializer

    group = group_serializer_class()(many=True, read_only=True)
    recipient = user_serializer_class()(many=True, read_only=True)
    seen_by = user_serializer_class()(many=True, read_only=True)
    title = SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "title",
            "recipient",
            "group",
            "verb",
            "status",
            "actor_content_type",
            "target_content_type",
            "action_object_content_type",
            "link",
            "is_sent",
            "seen_by",
            "public",
            "data",
            "timestamp",
        )

    def get_title(self, notification: Notification) -> str:
        """
        Compute the title of the notification.

        Args:
            notification: The notification instance.

        Returns:
            str: The computed title of the notification.
        """
        return str(notification)

    def to_representation(self, instance: Notification) -> Dict:
        """
        Customize the representation of the serialized data.

        Args:
            instance: The notification instance being serialized.

        Returns:
            dict: The serialized representation of the notification with non-empty fields.
        """
        data = super().to_representation(instance)
        return filter_non_empty_fields(data)
