import sys

import pytest
from unittest.mock import patch, MagicMock
from django_notification.settings.checks import check_notification_settings
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.settings,
    pytest.mark.settings_checks,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


class TestCheckNotificationSettings:
    @patch("django_notification.settings.checks.config")
    def test_valid_settings(self, mock_config: MagicMock) -> None:
        """
        Test that valid settings produce no errors.

        Args:
        ----
            mock_config (MagicMock): Mocked configuration object with valid settings.

        Asserts:
        -------
            No errors are returned when all settings are valid.
        """
        # Mock the config values to be valid
        mock_config.include_soft_delete = True
        mock_config.include_hard_delete = False
        mock_config.admin_has_add_permission = False
        mock_config.admin_has_change_permission = False
        mock_config.admin_has_delete_permission = False
        mock_config.include_serializer_full_details = True
        mock_config.exclude_serializer_null_fields = True
        mock_config.api_allow_list = True
        mock_config.api_allow_retrieve = False
        mock_config.user_serializer_fields = ["id", "username"]
        mock_config.api_ordering_fields = ["created_at"]
        mock_config.api_search_fields = ["title"]
        mock_config.staff_user_throttle_rate = "10/minute"
        mock_config.authenticated_user_throttle_rate = "5/minute"
        mock_config.get_setting.side_effect = lambda name, default: None

        errors = check_notification_settings(None)

        # There should be no errors for valid settings
        assert not errors

    @patch("django_notification.settings.checks.config")
    def test_invalid_boolean_settings(self, mock_config: MagicMock) -> None:
        """
        Test that invalid boolean settings return errors.

        Args:
        ----
            mock_config (MagicMock): Mocked configuration object with invalid boolean settings.

        Asserts:
        -------
            Three errors are returned for invalid boolean values in settings.
        """
        # Mock the config values with invalid boolean settings
        mock_config.include_soft_delete = "not_boolean"
        mock_config.include_hard_delete = "not_boolean"
        mock_config.admin_has_add_permission = "not_boolean"
        mock_config.admin_has_change_permission = "not_boolean"
        mock_config.admin_has_delete_permission = "not_boolean"
        mock_config.include_serializer_full_details = "not_bool"
        mock_config.exclude_serializer_null_fields = "not_boolean"
        mock_config.user_serializer_fields = ["id", "username"]
        mock_config.api_ordering_fields = ["created_at"]
        mock_config.api_search_fields = ["title"]
        mock_config.staff_user_throttle_rate = "10/minute"
        mock_config.authenticated_user_throttle_rate = "5/minute"
        mock_config.api_allow_list = "not_boolean"
        mock_config.api_allow_retrieve = True
        mock_config.get_setting.side_effect = lambda name, default: None

        errors = check_notification_settings(None)

        # Expect 8 errors for invalid boolean values
        assert len(errors) == 8
        assert (
            errors[0].id
            == f"django_notification.E001_{mock_config.prefix}API_INCLUDE_SOFT_DELETE"
        )
        assert (
            errors[1].id
            == f"django_notification.E001_{mock_config.prefix}API_INCLUDE_HARD_DELETE"
        )
        assert (
            errors[2].id
            == f"django_notification.E001_{mock_config.prefix}ADMIN_HAS_ADD_PERMISSION"
        )
        assert (
            errors[3].id
            == f"django_notification.E001_{mock_config.prefix}ADMIN_HAS_CHANGE_PERMISSION"
        )
        assert (
            errors[4].id
            == f"django_notification.E001_{mock_config.prefix}ADMIN_HAS_DELETE_PERMISSION"
        )
        assert (
                errors[5].id
                == f"django_notification.E001_{mock_config.prefix}SERIALIZER_INCLUDE_FULL_DETAILS"
        )
        assert (
                errors[6].id
                == f"django_notification.E001_{mock_config.prefix}SERIALIZER_EXCLUDE_NULL_FIELDS"
        )
        assert (
            errors[7].id
            == f"django_notification.E001_{mock_config.prefix}API_ALLOW_LIST"
        )

    @patch("django_notification.settings.checks.config")
    def test_invalid_list_settings(self, mock_config: MagicMock) -> None:
        """
        Test that invalid list settings return errors.

        Args:
        ----
            mock_config (MagicMock): Mocked configuration object with invalid list settings.

        Asserts:
        -------
            Three errors are returned for invalid list values in settings.
        """
        # Mock the config values with invalid list settings
        mock_config.include_soft_delete = True
        mock_config.include_hard_delete = False
        mock_config.admin_has_add_permission = False
        mock_config.admin_has_change_permission = False
        mock_config.admin_has_delete_permission = False
        mock_config.include_serializer_full_details = True
        mock_config.exclude_serializer_null_fields = True
        mock_config.api_allow_list = True
        mock_config.api_allow_retrieve = False
        mock_config.user_serializer_fields = []
        mock_config.api_ordering_fields = []
        mock_config.staff_user_throttle_rate = "10/minute"
        mock_config.authenticated_user_throttle_rate = "5/minute"
        mock_config.get_setting.side_effect = lambda name, default: None
        mock_config.api_search_fields = [123]  # Invalid list element

        errors = check_notification_settings(None)

        # Expect 3 errors for invalid list settings
        assert len(errors) == 3
        assert (
            errors[0].id
            == f"django_notification.E003_{mock_config.prefix}USER_SERIALIZER_FIELDS"
        )
        assert (
            errors[1].id
            == f"django_notification.E003_{mock_config.prefix}API_ORDERING_FIELDS"
        )
        assert (
            errors[2].id
            == f"django_notification.E004_{mock_config.prefix}API_SEARCH_FIELDS"
        )

    @patch("django_notification.settings.checks.config")
    def test_invalid_throttle_rate(self, mock_config: MagicMock) -> None:
        """
        Test that invalid throttle rates return errors.

        Args:
        ----
            mock_config (MagicMock): Mocked configuration object with invalid throttle rates.

        Asserts:
        -------
            Two errors are returned for invalid throttle rates.
        """
        # Mock the config values with invalid throttle rates
        mock_config.include_soft_delete = True
        mock_config.include_hard_delete = False
        mock_config.admin_has_add_permission = False
        mock_config.admin_has_change_permission = False
        mock_config.admin_has_delete_permission = False
        mock_config.include_serializer_full_details = True
        mock_config.exclude_serializer_null_fields = True
        mock_config.api_allow_list = True
        mock_config.api_allow_retrieve = False
        mock_config.user_serializer_fields = ["id", "username"]
        mock_config.api_ordering_fields = ["created_at"]
        mock_config.api_search_fields = ["title"]
        mock_config.get_setting.side_effect = lambda name, default: None
        mock_config.staff_user_throttle_rate = "invalid_rate"
        mock_config.authenticated_user_throttle_rate = "abc/hour"

        errors = check_notification_settings(None)

        # Expect 2 errors for invalid throttle rates
        assert len(errors) == 2
        assert errors[0].id == "django_notification.E005"
        assert errors[1].id == "django_notification.E007"

    @patch("django_notification.settings.checks.config")
    def test_invalid_class_import(self, mock_config: MagicMock) -> None:
        """
        Test that invalid class import settings return errors.

        Args:
        ----
            mock_config (MagicMock): Mocked configuration object with invalid class paths.

        Asserts:
        -------
            Seven errors are returned for invalid class imports.
        """
        # Mock the config values with invalid class paths
        mock_config.include_soft_delete = True
        mock_config.include_hard_delete = False
        mock_config.admin_has_add_permission = False
        mock_config.admin_has_change_permission = False
        mock_config.admin_has_delete_permission = False
        mock_config.include_serializer_full_details = True
        mock_config.exclude_serializer_null_fields = True
        mock_config.api_allow_list = True
        mock_config.api_allow_retrieve = False
        mock_config.user_serializer_fields = ["id", "username"]
        mock_config.api_ordering_fields = ["created_at"]
        mock_config.api_search_fields = ["title"]
        mock_config.staff_user_throttle_rate = "10/minute"
        mock_config.authenticated_user_throttle_rate = "5/minute"
        mock_config.get_setting.side_effect = (
            lambda name, default: "invalid.path.ClassName"
        )

        errors = check_notification_settings(None)

        # Expect 8 errors for invalid class imports
        assert len(errors) == 8
        assert (
            errors[0].id
            == f"django_notification.E010_{mock_config.prefix}USER_SERIALIZER_CLASS"
        )
        assert (
            errors[1].id
            == f"django_notification.E010_{mock_config.prefix}GROUP_SERIALIZER_CLASS"
        )
        assert (
            errors[2].id
            == f"django_notification.E010_{mock_config.prefix}API_THROTTLE_CLASS"
        )
        assert (
            errors[3].id
            == f"django_notification.E010_{mock_config.prefix}API_PAGINATION_CLASS"
        )
        assert (
            errors[4].id
            == f"django_notification.E011_{mock_config.prefix}API_PARSER_CLASSES"
        )
        assert (
            errors[5].id
            == f"django_notification.E010_{mock_config.prefix}API_FILTERSET_CLASS"
        )
        assert (
            errors[6].id
            == f"django_notification.E010_{mock_config.prefix}API_EXTRA_PERMISSION_CLASS"
        )
        assert (
                errors[7].id
                == f"django_notification.E010_{mock_config.prefix}ADMIN_SITE_CLASS"
        )
