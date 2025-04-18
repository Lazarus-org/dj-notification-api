import sys
from typing import Any, Dict
from unittest.mock import patch

import pytest
from pytest import mark

from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.constants.default_settings import default_serializer_settings
from django_notification.settings.conf import config
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON
from django_notification.utils.serialization.field_filters import (
    filter_non_empty_fields,
)
from django_notification.utils.serialization.notif_title_generator import generate_title

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_serializers,
    pytest.mark.api_serializers_dynamic_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


class TestNotificationDynamicSerializer:
    """
    Test suite for the NotificationDynamicSerializer class.

    This class contains tests for verifying the fields, title generation, and non-empty field filtering
    functionality of the NotificationDynamicSerializer.
    """

    @patch.object(config, "exclude_serializer_null_fields", False)
    @mark.django_db
    def test_title_generation(self, notification_dict: Dict[str, Any]) -> None:
        """
        Test that the NotificationDynamicSerializer generates the correct title for the notification.

        Args:
        ----
            notification_dict (Dict[str, Any]): A dictionary representing the notification data.

        Asserts:
        -------
            - The title generated by the serializer matches the expected title.
        """
        serializer = NotificationDynamicSerializer(notification_dict)
        assert serializer.data["title"] == generate_title(notification_dict)

    @mark.django_db
    def test_filter_non_empty_fields(self, notification_dict: Dict[str, Any]) -> None:
        """
        Test that the NotificationDynamicSerializer filters out empty fields from its output.

        Args:
        ----
            notification_dict (Dict[str, Any]): A dictionary representing the notification data.

        Asserts:
        -------
            - No fields in the serialized output have empty or None values.
        """
        serializer = NotificationDynamicSerializer(notification_dict)
        data = serializer.data
        for field, value in data.items():
            assert value is not None and value != "", f"Field {field} is empty"

    @mark.django_db
    def test_to_representation(self, notification_dict: Dict[str, Any]) -> None:
        """
        Test that the NotificationDynamicSerializer's to_representation method correctly processes the notification data.

        Args:
        ----
            notification_dict (Dict[str, Any]): A dictionary representing the notification data.

        Asserts:
        -------
            - The output of to_representation matches the filtered non-empty fields of the serializer's data.
        """
        serializer = NotificationDynamicSerializer(notification_dict)
        data = serializer.to_representation(notification_dict)
        assert data == filter_non_empty_fields(
            super(NotificationDynamicSerializer, serializer).to_representation(
                notification_dict
            )
        )
