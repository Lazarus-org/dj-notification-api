from typing import Any, List

from django.core.checks import Error, register

from django_notification.models import Notification
from django_notification.settings.conf import config
from django_notification.utils.get_model_fields import get_model_fields
from django_notification.validators.config_validators import (
    validate_boolean_setting,
    validate_list_fields,
    validate_optional_class_setting,
    validate_optional_classes_setting,
    validate_throttle_rate,
)


@register()
def check_notification_settings(app_configs: Any, **kwargs: Any) -> List[Error]:
    """Check and validate notification settings in the Django configuration.

    This function performs validation of various notification-related settings
    defined in the Django settings. It returns a list of errors if any issues are found.

    Parameters:
    -----------
    app_configs : Any
        Passed by Django during checks (not used here).

    kwargs : Any
        Additional keyword arguments for flexibility.

    Returns:
    --------
    List[Error]
        A list of `Error` objects for any detected configuration issues.

    """
    errors: List[Error] = []

    # Validate boolean settings
    errors.extend(
        validate_boolean_setting(
            config.include_soft_delete, f"{config.prefix}API_INCLUDE_SOFT_DELETE"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.include_hard_delete, f"{config.prefix}API_INCLUDE_HARD_DELETE"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_add_permission,
            f"{config.prefix}ADMIN_HAS_ADD_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_change_permission,
            f"{config.prefix}ADMIN_HAS_CHANGE_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_delete_permission,
            f"{config.prefix}ADMIN_HAS_DELETE_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.include_serializer_full_details,
            f"{config.prefix}SERIALIZER_INCLUDE_FULL_DETAILS",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.exclude_serializer_null_fields,
            f"{config.prefix}SERIALIZER_EXCLUDE_NULL_FIELDS",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.api_allow_list, f"{config.prefix}API_ALLOW_LIST"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.api_allow_retrieve, f"{config.prefix}API_ALLOW_RETRIEVE"
        )
    )

    errors.extend(
        validate_list_fields(
            config.notification_serializer_fields,
            f"{config.prefix}SERIALIZER_FIELDS",
            available_fields=["title"] + get_model_fields(Notification),
            allow_none=True,
        )
    )

    errors.extend(
        validate_list_fields(
            config.user_serializer_fields, f"{config.prefix}USER_SERIALIZER_FIELDS"
        )
    )

    errors.extend(
        validate_list_fields(
            config.api_ordering_fields, f"{config.prefix}API_ORDERING_FIELDS"
        )
    )

    errors.extend(
        validate_list_fields(
            config.api_search_fields, f"{config.prefix}API_SEARCH_FIELDS"
        )
    )

    errors.extend(
        validate_throttle_rate(
            config.staff_user_throttle_rate,
            f"{config.prefix}STAFF_USER_THROTTLE_RATE",
        )
    )
    errors.extend(
        validate_throttle_rate(
            config.authenticated_user_throttle_rate,
            f"{config.prefix}AUTHENTICATED_USER_THROTTLE_RATE",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}SERIALIZER_CLASS", None),
            f"{config.prefix}SERIALIZER_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}USER_SERIALIZER_CLASS", None),
            f"{config.prefix}USER_SERIALIZER_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}GROUP_SERIALIZER_CLASS", None),
            f"{config.prefix}GROUP_SERIALIZER_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}API_THROTTLE_CLASS", None),
            f"{config.prefix}API_THROTTLE_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}API_PAGINATION_CLASS", None),
            f"{config.prefix}API_PAGINATION_CLASS",
        )
    )
    errors.extend(
        validate_optional_classes_setting(
            config.get_setting(f"{config.prefix}API_PARSER_CLASSES", []),
            f"{config.prefix}API_PARSER_CLASSES",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}API_FILTERSET_CLASS", None),
            f"{config.prefix}API_FILTERSET_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}API_EXTRA_PERMISSION_CLASS", None),
            f"{config.prefix}API_EXTRA_PERMISSION_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting(f"{config.prefix}ADMIN_SITE_CLASS", None),
            f"{config.prefix}ADMIN_SITE_CLASS",
        )
    )

    return errors
