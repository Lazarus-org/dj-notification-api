"""Server-side channel opt-outs, independent of personal inbox visibility."""

from django_notification.models.notification_category import NotificationCategory
from django_notification.models.notification_channel_preference import (
    NotificationChannelPreference,
)


def channel_enabled(user_id, category_id, channel, database="default"):
    """Mandatory categories cannot be suppressed by per-channel opt-outs."""
    category = (
        NotificationCategory.objects.using(database)
        .filter(pk=category_id)
        .values("is_mandatory")
        .first()
    )
    if category is None:
        return False
    if category["is_mandatory"]:
        return True
    return (
        not NotificationChannelPreference.objects.using(database)
        .filter(
            user_id=user_id,
            category_id=category_id,
            channel=channel,
            enabled=False,
        )
        .exists()
    )


def blocked_channels_for_users(user_ids, category_id, channels, database):
    """Load disabled (user, channel) pairs per bounded recipient batch."""
    rows = NotificationChannelPreference.objects.using(database).filter(
        user_id__in=user_ids,
        category_id=category_id,
        channel__in=channels,
        enabled=False,
    )
    return set(rows.values_list("user_id", "channel"))
