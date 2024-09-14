import sys
from unittest.mock import patch
from django_notification.validators.config_validators import (
    validate_boolean_setting,
    validate_list_fields,
    validate_throttle_rate,
    validate_optional_class_setting,
    validate_optional_classes_setting,
)
import pytest
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.validators,
    pytest.mark.config_validators,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


class TestValidateBooleanSetting:
    def test_valid_boolean(self) -> None:
        """
        Test that a valid boolean setting returns no errors.

        Args:
        ----
            None

        Asserts:
        -------
            The result should have no errors.
        """
        errors = validate_boolean_setting(True, "SOME_BOOLEAN_SETTING")
        assert not errors  # No errors should be returned

    def test_invalid_boolean(self) -> None:
        """
        Test that a non-boolean setting returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID.
        """
        errors = validate_boolean_setting("not_boolean", "SOME_BOOLEAN_SETTING")  # type: ignore
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E001_SOME_BOOLEAN_SETTING"


class TestValidateListFields:
    def test_valid_list(self) -> None:
        """
        Test that a valid list of fields returns no errors.

        Args:
        ----
            None

        Asserts:
        -------
            The result should have no errors.
        """
        errors = validate_list_fields(["field1", "field2"], "SOME_LIST_SETTING")
        assert not errors  # No errors should be returned

    def test_invalid_list_type(self) -> None:
        """
        Test that a non-list setting returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID.
        """
        errors = validate_list_fields("not_a_list", "SOME_LIST_SETTING")  # type: ignore
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E002_SOME_LIST_SETTING"

    def test_empty_list(self) -> None:
        """
        Test that an empty list returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID.
        """
        errors = validate_list_fields([], "SOME_LIST_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E003_SOME_LIST_SETTING"

    def test_invalid_element_in_list(self) -> None:
        """
        Test that a list containing a non-string element returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID.
        """
        errors = validate_list_fields([123, "valid_field"], "SOME_LIST_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E004_SOME_LIST_SETTING"


class TestValidateThrottleRate:
    def test_valid_throttle_rate(self) -> None:
        """
        Test that a valid throttle rate returns no errors.

        Args:
        ----
            None

        Asserts:
        -------
            The result should have no errors.
        """
        errors = validate_throttle_rate("10/minute", "THROTTLE_RATE_SETTING")
        assert not errors

    def test_invalid_format(self) -> None:
        """
        Test that an invalid format for throttle rate returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for invalid formats.
        """
        errors = validate_throttle_rate("invalid_rate", "THROTTLE_RATE_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E005"

        errors = validate_throttle_rate("invalid/type/given", "THROTTLE_RATE_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E006"

    def test_invalid_time_unit(self) -> None:
        """
        Test that an invalid time unit in throttle rate returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for invalid time units.
        """
        errors = validate_throttle_rate("10/century", "THROTTLE_RATE_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E008"

    def test_non_numeric_rate(self) -> None:
        """
        Test that a non-numeric rate part returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for non-numeric rates.
        """
        errors = validate_throttle_rate("abc/minute", "THROTTLE_RATE_SETTING")
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E007"


class TestValidateOptionalClassSetting:
    def test_valid_class_import(self) -> None:
        """
        Test that a valid class path returns no errors.

        Args:
        ----
            None

        Asserts:
        -------
            The result should have no errors.
        """
        with patch("django.utils.module_loading.import_string"):
            errors = validate_optional_class_setting(
                "django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle",
                "SOME_CLASS_SETTING",
            )
            assert not errors

    def test_invalid_class_import(self) -> None:
        """
        Test that an invalid class path returns an import error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for invalid class paths.
        """
        with patch(
            "django.utils.module_loading.import_string", side_effect=ImportError
        ):
            errors = validate_optional_class_setting(
                "invalid.path.ClassName", "SOME_CLASS_SETTING"
            )
            assert len(errors) == 1
            assert errors[0].id == "django_notification.E010_SOME_CLASS_SETTING"

    def test_invalid_class_path_type(self) -> None:
        """
        Test that a non-string class path returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for non-string class paths.
        """
        errors = validate_optional_class_setting(12345, "SOME_CLASS_SETTING")  # type: ignore
        assert len(errors) == 1
        assert errors[0].id == "django_notification.E009_SOME_CLASS_SETTING"

    def test_none_class_path(self) -> None:
        """
        Test that a None class path returns no error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should have no errors.
        """
        errors = validate_optional_class_setting(None, "SOME_CLASS_SETTING")  # type: ignore
        assert not errors

    def test_invalid_list_args_classes_import(self) -> None:
        """
        Test that a list of invalid classes args returns an error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain errors for each invalid class path with the expected error ID.
        """
        errors = validate_optional_classes_setting(
            [1, 5], "SOME_CLASS_SETTING"  # type: ignore
        )
        assert len(errors) == 2
        assert errors[0].id == "django_notification.E012_SOME_CLASS_SETTING"

    def test_invalid_path_classes_import(self) -> None:
        """
        Test that a list of invalid classes path returns an import error.

        Args:
        ----
            None

        Asserts:
        -------
            The result should contain one error with the expected error ID for invalid class paths.
        """
        with patch(
            "django.utils.module_loading.import_string", side_effect=ImportError
        ):
            errors = validate_optional_classes_setting(
                ["INVALID_PATH"], "SOME_CLASS_SETTING"
            )
            assert len(errors) == 1
            assert errors[0].id == "django_notification.E013_SOME_CLASS_SETTING"
