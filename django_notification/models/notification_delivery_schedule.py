"""Per-user delivery cadence and quiet hours for external channels."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .notification_channel_preference import CHANNEL_CHOICES


class DeliveryFrequency(models.TextChoices):
    """Frequency applies to optional notifications, never mandatory/urgent."""

    IMMEDIATE = "IMMEDIATE", "Immediately"
    DAILY = "DAILY", "Daily email digest"
    WEEKLY = "WEEKLY", "Weekly email digest"


class NotificationDeliverySchedule(models.Model):
    """One user's settings per channel; no row means immediate delivery."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_delivery_schedules",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES)
    frequency = models.CharField(
        max_length=9,
        choices=DeliveryFrequency.choices,
        default=DeliveryFrequency.IMMEDIATE,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    quiet_start = models.TimeField(null=True, blank=True)
    quiet_end = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_delivery_schedule"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "channel"),
                name="djnotify_unique_delivery_schedule",
            ),
        ]

    def clean(self):
        """Reject inconsistent schedules from the admin or application code."""
        super().clean()
        from django_notification.delivery.scheduling import valid_zone

        valid_zone(self.timezone)
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValidationError("Both quiet-hour boundaries are required")
        if self.frequency != DeliveryFrequency.IMMEDIATE and self.channel != "email":
            raise ValidationError("Digests are supported for email only")

    def __str__(self):
        """Do not include a personal identifier."""
        return f"Delivery schedule ({self.channel})"
