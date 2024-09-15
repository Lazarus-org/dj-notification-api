from typing import List

from django.core.checks import Error
from django.utils.module_loading import import_string

VALID_TIME_UNITS = ["second", "minute", "hour", "day"]


def validate_boolean_setting(value: bool, config_name: str) -> List[Error]:
    errors: List[Error] = []
    if not isinstance(value, bool):
        errors.append(
            Error(
                f"{config_name} is not a boolean.",
                hint=f"Ensure {config_name} is either True or False.",
                id=f"django_notification.E001_{config_name}",
            )
        )
    return errors


def validate_list_fields(
    fields: List[str],
    config_name: str,
) -> List[Error]:
    errors = []
    if not isinstance(fields, list):
        errors.append(
            Error(
                f"{config_name} is not a list.",
                hint=f"Ensure {config_name} is a list of fields.",
                id=f"django_notification.E002_{config_name}",
            )
        )
    elif not fields:
        errors.append(
            Error(
                f"{config_name} is an empty list.",
                hint=f"Ensure {config_name} contains at least one field.",
                id=f"django_notification.E003_{config_name}",
            )
        )
    else:
        for field in fields:
            if not isinstance(field, str):
                errors.append(
                    Error(
                        f"Invalid type in {config_name}: {field} is not a string.",
                        hint=f"Ensure all elements in {config_name} are strings.",
                        id=f"django_notification.E004_{config_name}",
                    )
                )

    return errors


def validate_throttle_rate(rate: str, setting_name: str) -> List[Error]:
    """
    Validates that a throttle rate is in the correct format: `{number}/{time_unit}`.

    Args:
        rate (str): The throttle rate to validate, e.g., "10/minute".
        setting_name (str): The name of the setting being validated (for error reporting).

    Returns:
        List[Error]: A list of errors if the rate is not valid, otherwise an empty list.
    """
    errors = []
    if not isinstance(rate, str) or "/" not in rate:
        errors.append(
            Error(
                f"'{setting_name}' must be an string in the format 'number/time_unit' (e.g., '10/minute').",
                id="django_notification.E005",
            )
        )
        return errors

    # Split the rate into the number and the time unit
    parts = rate.split("/")
    if len(parts) != 2:
        errors.append(
            Error(
                f"'{setting_name}' is not in the correct format. Expected 'number/time_unit'.",
                id="django_notification.E006",
            )
        )
        return errors

    number, time_unit = parts

    # Check if the number part is a valid integer
    if not number.isdigit():
        errors.append(
            Error(
                f"'{setting_name}' must start with a valid integer. Found: '{number}'.",
                id="django_notification.E007",
            )
        )

    # Check if the time unit is valid
    if time_unit not in VALID_TIME_UNITS:
        errors.append(
            Error(
                f"'{setting_name}' has an invalid time unit: '{time_unit}'.",
                hint=f"Valid time units are: {', '.join(VALID_TIME_UNITS)}.",
                id="django_notification.E008",
            )
        )

    return errors


def validate_optional_class_setting(
    setting_value: str, setting_name: str
) -> List[Error]:
    """Validate that the setting is a valid class path and can be imported.

    Args:
        setting_value (str): The value of the setting to validate, typically a class path.
        setting_name (str): The name of the setting being validated (for error reporting).

    Returns:
        List[Error]: A list of validation errors, or an empty list if valid.

    """
    errors: List[Error] = []

    if setting_value is None:
        # If the setting is None, we consider it optional and valid
        return errors

    if not isinstance(setting_value, str):
        errors.append(
            Error(
                f"The setting '{setting_name}' must be a valid string representing a class path.",
                hint=f"Ensure '{setting_name}' is set to a string (e.g., 'myapp.module.MyClass').",
                id=f"django_notification.E009_{setting_name}",
            )
        )
        return errors

    # Attempt to import the class from the given path
    try:
        import_string(setting_value)
    except ImportError:
        errors.append(
            Error(
                f"Cannot import the class from the setting '{setting_name}'.",
                hint=f"Ensure the class path '{setting_value}' is valid and importable.",
                id=f"django_notification.E010_{setting_name}",
            )
        )

    return errors


def validate_optional_classes_setting(
    setting_value: List[str], setting_name: str
) -> List[Error]:
    """Validate that the setting value is a list of class paths and ensure that
    they can be imported.

    Args:
        setting_value (List[str]): The setting value to validate, typically a list of class paths.
        setting_name (str): The name of the setting being validated (for error reporting).

    Returns:
        List[Error]: A list of validation errors, or an empty list if the setting is valid.

    """
    errors: List[Error] = []

    # If the setting is None, it's optional, so we consider it valid.
    if setting_value is None:
        return errors

    if not isinstance(setting_value, list):
        errors.append(
            Error(
                f"Invalid type for setting '{setting_name}'.",
                hint="The setting must be either a list of strings. (e.g., ['myapp.module.MyClass'])",
                id=f"django_notification.E011_{setting_name}",
            )
        )
        return errors

    # Validate each path in the list
    for path in setting_value:
        if not isinstance(path, str):
            errors.append(
                Error(
                    f"Invalid type for class path in '{setting_name}'.",
                    hint="Each item in the list must be a valid string representing a class path.",
                    id=f"django_notification.E012_{setting_name}",
                )
            )
        else:
            # Attempt to import the class from the given path
            try:
                import_string(path)
            except ImportError:
                errors.append(
                    Error(
                        f"Cannot import the class from '{path}' in setting '{setting_name}'.",
                        hint=f"Ensure that '{path}' is a valid importable class path.",
                        id=f"django_notification.E013_{setting_name}",
                    )
                )

    return errors
