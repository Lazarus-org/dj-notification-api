"""Per-user opt-outs for individual external notification channels."""

from django.conf import settings
from django.db import models

CHANNEL_CHOICES = (
    ("email", "Email"),
    ("sms", "SMS"),
    ("push", "Push"),
    ("webhook", "Webhook"),
)
CHANNEL_VALUES = frozenset(value for value, _ in CHANNEL_CHOICES)


class NotificationChannelPreference(models.Model):
    """An absent override means enabled; mandatory categories always win."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_channel_preferences",
    )
    category = models.ForeignKey(
        "django_notification.NotificationCategory",
        on_delete=models.CASCADE,
        related_name="channel_preferences",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_channel_preference"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "category", "channel"),
                name="djnotify_unique_channel_preference",
            ),
        ]

    def __str__(self):
        """Do not expose user identifiers in string representations."""
        return f"{self.category_id}:{self.channel}"
