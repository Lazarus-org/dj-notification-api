from typing import Any, List

from django.core.checks import Error, register

from django_notification.settings.conf import config
from django_notification.validators.config_validators import (
    validate_boolean_setting,
    validate_list_fields,
    validate_throttle_rate,
    validate_optional_class_setting,
    validate_optional_classes_setting,
)


@register()
def check_notification_settings(app_configs: Any, **kwargs: Any) -> List[Error]:
    """
    Check and validate notification settings in the Django configuration.

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
            config.include_soft_delete, "DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.include_hard_delete, "DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_add_permission,
            "DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_change_permission,
            "DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.admin_has_delete_permission,
            "DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.include_serializer_full_details,
            "DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.api_allow_list, "DJANGO_NOTIFICATION_API_ALLOW_LIST"
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.api_allow_retrieve, "DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE"
        )
    )

    errors.extend(
        validate_list_fields(
            config.user_serializer_fields, "DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS"
        )
    )

    errors.extend(
        validate_list_fields(
            config.api_ordering_fields, "DJANGO_NOTIFICATION_API_ORDERING_FIELDS"
        )
    )

    errors.extend(
        validate_list_fields(
            config.api_search_fields, "DJANGO_NOTIFICATION_API_SEARCH_FIELDS"
        )
    )

    errors.extend(
        validate_throttle_rate(
            config.staff_user_throttle_rate,
            "DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE",
        )
    )
    errors.extend(
        validate_throttle_rate(
            config.authenticated_user_throttle_rate,
            "DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS", None),
            "DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS", None),
            "DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_API_THROTTLE_CLASS", None),
            "DJANGO_NOTIFICATION_API_THROTTLE_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_API_PAGINATION_CLASS", None),
            "DJANGO_NOTIFICATION_API_PAGINATION_CLASS",
        )
    )
    errors.extend(
        validate_optional_classes_setting(
            config.get_setting("DJANGO_NOTIFICATION_API_PARSER_CLASSES", []),
            "DJANGO_NOTIFICATION_API_PARSER_CLASSES",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_API_FILTERSET_CLASS", None),
            "DJANGO_NOTIFICATION_API_FILTERSET_CLASS",
        )
    )
    errors.extend(
        validate_optional_class_setting(
            config.get_setting("DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS", None),
            "DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS",
        )
    )

    return errors
