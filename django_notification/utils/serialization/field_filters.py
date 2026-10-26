def filter_non_empty_fields(data: dict, exclude_fields: list | None = None) -> dict:
    """Filters out empty fields and sensitive fields from the given data.

    Args:
        data (dict): The original data to filter.
        exclude_fields (list): List of fields to exclude from the filtered result (e.g., sensitive fields like 'password').

    Returns:
        dict: A dictionary containing only non-empty and non-excluded fields.

    """
    exclude_fields = exclude_fields or []
    return {
        field_name: field_value
        for field_name, field_value in data.items()
        if field_value not in (None, "", [], {}) and field_name not in exclude_fields
    }
