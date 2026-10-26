"""Durable email digest envelopes, separate from individual delivery jobs."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .notification_delivery import DeliveryStatus


class NotificationDigest(models.Model):
    """One recipient, channel and delivery slot; safely replayable by workers."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_digests",
    )
    channel = models.CharField(max_length=16, default="email")
    scheduled_at = models.DateTimeField()
    status = models.CharField(
        max_length=12,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_digest"
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "channel", "scheduled_at"),
                name="djnotify_unique_digest_slot",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_digest_ready_idx",
            ),
            models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_digest_lease_idx",
            ),
        ]

    def __str__(self):
        """Avoid leaking the recipient's email in logs."""
        return f"Digest #{self.pk} ({self.status})"
