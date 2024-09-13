from rest_framework import serializers

from django_notification.settings.conf import config
from django_notification.utils.user_model import UserModel


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserModel, designed to include user-specific fields as configured.

    This serializer is responsible for converting `UserModel` instances to JSON format and vice versa.
    It includes fields specified in the `config.user_serializer_fields` configuration setting.

    Attributes:
        Meta (class): Configuration for the serializer, including the model and fields to be serialized.

    """

    class Meta:
        model = UserModel
        fields = config.user_serializer_fields
