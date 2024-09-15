from typing import Type

from rest_framework.serializers import BaseSerializer

from django_notification.api.serializers import GroupSerializer, UserSerializer
from django_notification.settings.conf import config


def group_serializer_class():
    """
    Get the serializer class for the group field, either from config or the default.
    """
    return config.group_serializer_class or GroupSerializer


def user_serializer_class() -> Type[BaseSerializer]:
    """
    Get the serializer class for the recipient and seen_by fields, either from config or the default.
    """
    return config.user_serializer_class or UserSerializer
