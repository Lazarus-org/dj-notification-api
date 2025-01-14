import sys
from typing import Any, Dict

import pytest
from django.utils.timezone import now, timedelta

from django_notification.models import Notification
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON
from django_notification.utils.serialization.notif_title_generator import generate_title

pytestmark = [
    pytest.mark.utils,
    pytest.mark.utils_title_generator,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


class TestGenerateTitle:
    """
    Test suite for the `generate_title` utility.
    """

    @pytest.mark.parametrize(
        "notification_dict, expected_title",
        [
            (
                {
                    "description": "Task completed",
                },
                "Task completed",
            ),
            (
                {"description": "New message", "timestamp": now() - timedelta(hours=2)},
                "New message 2 hours ago",
            ),
            (
                {
                    "description": "Appointment reminder",
                    "timestamp": now() - timedelta(days=1),
                },
                "Appointment reminder 1 day ago",
            ),
        ],
    )
    def test_generate_title_with_valid_data(
        self, notification_dict: Dict[str, Any], expected_title: str
    ) -> None:
        """
        Test that `generate_title` correctly formats the title when provided with valid data.

        Args:
        ----
            notification_dict (Dict[str, Any]): Dictionary containing notification data.
            expected_title (str): The expected formatted title.

        Asserts:
        -------
            The result of `generate_title` should match the expected title when valid data is provided.
        """
        result = generate_title(notification_dict)
        # Normalize the spaces in both expected and actual results
        assert result.replace("\xa0", " ") == expected_title

    def test_generate_title_with_non_dict(self, notification: Notification) -> None:
        """
        Test that `generate_title` raises a ValueError when the input is not a dictionary.

        Args:
        ----
            notification (Notification): Notification instance (used to simulate non-dict input).

        Asserts:
        -------
            `generate_title` should raise a ValueError when the input is not a dictionary.
        """
        with pytest.raises(ValueError):
            generate_title(notification)  # type: ignore

    def test_generate_title_with_no_description(
        self, notification_dict: Dict[str, Any]
    ) -> None:
        """
        Test that `generate_title` raises a ValueError when the description key is missing.

        Args:
        ----
            notification_dict (Dict[str, Any]): Dictionary containing notification data (with the description key removed).

        Asserts:
        -------
            `generate_title` should raise a ValueError when the description key is missing.
        """
        notification_dict.pop("description")
        with pytest.raises(ValueError):
            generate_title(notification_dict)

    def test_generate_title_with_invalid_data(self) -> None:
        """
        Test that `generate_title` raises a ValueError when the input is not a dictionary.

        Args:
        ----
            None

        Asserts:
        -------
            `generate_title` should raise a ValueError when the input is a string (or other invalid data type).
        """
        with pytest.raises(ValueError):
            generate_title("invalid_data")  # type: ignore
