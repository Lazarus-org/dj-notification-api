from typing import Any

from django.conf import settings
from django.core.checks import Error, register

from django_notification.models import Notification
from django_notification.settings.conf import config
from django_notification.utils.get_model_fields import get_serializable_model_fields
from django_notification.validators.config_validators import (
    validate_boolean_setting,
    validate_list_fields,
    validate_optional_class_setting,
    validate_optional_classes_setting,
    validate_throttle_rate,
)


@register()
def check_notification_settings(app_configs: Any, **kwargs: Any) -> list[Error]:
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
    errors: list[Error] = []
    mode = getattr(settings, "DJANGO_NOTIFICATION_API_EVENT_DELIVERY", "signal")
    if mode not in ("signal", "outbox"):
        errors.append(
            Error(
                "DJANGO_NOTIFICATION_API_EVENT_DELIVERY must be 'signal' or 'outbox'",
                id="django_notification.E001",
            )
        )

    # External delivery is opt-in and must use durable event intent.
    # Reject incorrect backend paths at system-check time rather than
    # silently acknowledging an outbox event without creating jobs.
    from django.core.exceptions import ImproperlyConfigured

    from django_notification.delivery.registry import backend_paths, load_backend

    try:
        channels = backend_paths()
        if channels and mode != "outbox":
            errors.append(
                Error(
                    "External delivery requires EVENT_DELIVERY='outbox'",
                    id="django_notification.E002",
                )
            )
        for channel in channels:
            load_backend(channel)
    except ImproperlyConfigured:
        errors.append(
            Error(
                "Invalid DJANGO_NOTIFICATION_DELIVERY_BACKENDS configuration",
                id="django_notification.E003",
            )
        )

    # Locale customization applies only to optional delivery rendering.
    from django_notification.delivery.rendering import normalize_locale

    default_locale = getattr(
        settings,
        "DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE",
        settings.LANGUAGE_CODE,
    )
    if normalize_locale(default_locale) is None:
        errors.append(
            Error(
                "Invalid DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE",
                id="django_notification.E004",
            )
        )

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
        validate_boolean_setting(
            config.api_allow_legacy_get_mutations,
            f"{config.prefix}API_ALLOW_LEGACY_GET_MUTATIONS",
        )
    )
    errors.extend(
        validate_boolean_setting(
            config.api_retrieve_marks_seen,
            f"{config.prefix}API_RETRIEVE_MARKS_SEEN",
        )
    )

    errors.extend(
        validate_list_fields(
            config.notification_serializer_fields,
            f"{config.prefix}SERIALIZER_FIELDS",
            available_fields=["title"] + get_serializable_model_fields(Notification),
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
