import sys

import pytest
from unittest.mock import patch
from django_notification.settings.conf import NotificationConfig
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.settings,
    pytest.mark.settings_conf,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationConfig:
    """
    Test the exception handling in NotificationAppConfig for optional class imports.
    """

    def test_import_error_handling(self) -> None:
        """
        Test that `get_optional_classes` handles ImportError and returns None when an invalid class path is provided.

        Args:
        ----
            None

        Asserts:
        -------
            The result of `get_optional_classes` should be None when ImportError is raised.
        """
        config = NotificationConfig()

        with patch(
            "django.utils.module_loading.import_string", side_effect=ImportError
        ):
            result = config.get_optional_classes(
                "INVALID_SETTING", "invalid.path.ClassName"
            )
            assert result is None

    def test_invalid_class_path_handling(self) -> None:
        """
        Test that `get_optional_classes` returns None when an invalid class path is given (non-string).

        Args:
        ----
            None

        Asserts:
        -------
            The result of `get_optional_classes` should be None when a non-string path is provided.
        """
        config = NotificationConfig()
        result = config.get_optional_classes("INVALID_SETTING", None)
        assert result is None

        result = config.get_optional_classes("INVALID_SETTING", ["INVALID_PATH"])
        assert not result
