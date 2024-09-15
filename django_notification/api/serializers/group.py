from typing import Dict, List

from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from django_notification.utils.serialization.field_filters import (
    filter_non_empty_fields,
)


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for the Permission model.

    This serializer includes all fields of the Permission model.

    """

    class Meta:
        model = Permission
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for the Group model.

    This serializer includes all fields of the Group model and
    serializes associated permissions using the PermissionSerializer. It
    also filters out non-empty fields from the representation.

    """

    permissions: serializers.SerializerMethodField = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = "__all__"

    def get_permissions(self, obj: Group) -> List[Dict]:
        """Returns a list of permissions associated with the group.

        Args:
            obj (Group): The group instance being serialized.

        Returns:
            list[dict]: A list of serialized permissions.

        """
        serializer = PermissionSerializer(obj.permissions.all(), many=True)
        return serializer.data

    def to_representation(self, instance: Group) -> Dict:
        """Customize the representation of the Group instance by filtering out
        non-empty fields.

        Args:
            instance (Group): The group instance being serialized.

        Returns:
            dict: The serialized and filtered representation of the group.

        """
        data = super().to_representation(instance)
        return filter_non_empty_fields(data)
