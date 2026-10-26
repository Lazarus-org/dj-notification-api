"""Independent, inspectable delivery state for optional external channels."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeliveryStatus(models.TextChoices):
    """Delivery job states; none implies an HTTP/inbox read state."""

    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class AttemptStatus(models.TextChoices):
    """Outcome of an invocation of one external backend."""

    SUCCEEDED = "SUCCEEDED", "Succeeded"
    RETRY = "RETRY", "Retry scheduled"
    FAILED = "FAILED", "Permanent failure"


class NotificationDelivery(models.Model):
    """One notification x user x channel; unique across outbox event replays.

    The job stores no recipient address, token or message content. A hard delete of the
    notification or user cascades to queued delivery jobs.

    """

    notification = models.ForeignKey(
        "django_notification.Notification",
        on_delete=models.CASCADE,
        related_name="external_deliveries",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_notification_deliveries",
    )
    channel = models.CharField(max_length=16)
    digest = models.ForeignKey(
        "django_notification.NotificationDigest",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    status = models.CharField(
        max_length=12,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    retry_attempts = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=("notification", "recipient", "channel"),
                name="djnotify_unique_delivery_target_channel",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_deliv_ready_idx",
            ),
            models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_deliv_lease_idx",
            ),
        ]

    def __str__(self):
        """Avoid showing contact information in admin/logging."""
        return f"Delivery #{self.pk} ({self.channel}: {self.status})"


class NotificationDeliveryAttempt(models.Model):
    """Sanitized attempt history; never store backend exception text."""

    delivery = models.ForeignKey(
        NotificationDelivery,
        on_delete=models.CASCADE,
        related_name="attempt_history",
    )
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=AttemptStatus.choices)
    code = models.CharField(max_length=48)
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notification_delivery_attempt"
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(
                fields=("delivery", "number"),
                name="djnotify_unique_delivery_attempt",
            ),
        ]

    def __str__(self):
        """Display state without external-provider metadata."""
        return f"Attempt #{self.number} ({self.status})"
