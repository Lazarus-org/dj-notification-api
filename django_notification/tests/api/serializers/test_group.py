import sys
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from rest_framework.exceptions import ValidationError
from django_notification.api.serializers.group import GroupSerializer
from django_notification.settings.conf import config
from django_notification.utils.serialization.field_filters import (
    filter_non_empty_fields,
)
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_serializers,
    pytest.mark.api_serializers_group,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestGroupSerializer:
    """
    Test the GroupSerializer and PermissionSerializer functionality.
    """

    @patch.object(config, "exclude_serializer_null_fields", False)
    def test_group_serializer_with_valid_data(self, group_with_perm: Group) -> None:
        """
        Test that the GroupSerializer correctly serializes a group with permissions.

        Args:
        ----
            group_with_perm (Group): A group instance with associated permissions.

        Asserts:
        -------
            - The serialized data matches the group name and permissions.
            - The permissions field contains the expected data.
            - The filter_non_empty_fields function is applied correctly.
        """
        serializer = GroupSerializer(group_with_perm)
        serialized_data = serializer.data

        # Ensure that the correct data is serialized
        assert serialized_data["name"] == group_with_perm.name
        assert (
            len(serialized_data["permissions"]) == group_with_perm.permissions.count()
        )
        assert serialized_data["permissions"][0]["codename"] == "add_user"

        # Ensure the filter_non_empty_fields is applied
        filtered_data = filter_non_empty_fields(serialized_data)
        assert filtered_data == serializer.data

    def test_group_serializer_with_no_permissions(self) -> None:
        """
        Test that the GroupSerializer handles a group with no permissions correctly.

        Asserts:
        -------
            - The serialized data correctly represents a group with no permissions.
            - The permissions field is absent or null.
        """
        group = Group.objects.create(name="Editors")
        serializer = GroupSerializer(group)
        serialized_data = serializer.data

        # Ensure the serialized data is correct
        assert serialized_data["name"] == group.name
        assert serialized_data.get("permissions") is None

    def test_group_serializer_with_invalid_data(self) -> None:
        """
        Test that the GroupSerializer raises a ValidationError when provided with invalid data.

        Asserts:
        -------
            - The serializer raises a ValidationError when invalid data is passed.
        """
        invalid_data = {"name": self}
        serializer = GroupSerializer(data=invalid_data)

        # Ensure the serializer raises a validation error
        with pytest.raises(ValidationError):
            assert not serializer.is_valid(raise_exception=True)
