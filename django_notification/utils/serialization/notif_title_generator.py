from typing import Any, Dict

from django.contrib.humanize.templatetags.humanize import naturaltime


def generate_title(notification: Dict[str, Any]) -> str:
    """
    Generate the title for the notification if it is a dictionary, (when using values() method in queryset).

    Args:
        notification (dict): A dictionary representing the notification retrieved from the queryset.

    Returns:
        str: The title of the notification, including its description and the time since the timestamp.
    """
    try:
        description = notification.get("description")
        if description:
            timestamp = notification.get("timestamp")
            if timestamp:
                time_since = naturaltime(timestamp)
                return f"{description} {time_since}"

            return description

        raise ValueError("No description provided.")

    except AttributeError:
        raise ValueError(
            "The notification must be a dictionary with 'description' and 'timestamp' keys."
        )
