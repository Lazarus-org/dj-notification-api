"""Durable, minimal notification lifecycle events awaiting delivery."""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class OutboxStatus(models.TextChoices):
    """Internal claim and retry states."""

    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"


class NotificationOutboxEvent(models.Model):
    """One event written atomically with the related notification mutation.

    This model intentionally has no foreign key to Notification or User: an
    event about a hard-deleted record must survive cascading database deletes.
    Payload contains only the safe metadata in ``NotificationEvent``.

    """

    kind = models.CharField(max_length=64)
    payload = models.JSONField(encoder=DjangoJSONEncoder)
    status = models.CharField(
        max_length=12, choices=OutboxStatus.choices, default=OutboxStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_outbox_event"
        ordering = ("pk",)
        indexes = [
            models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_outbox_ready_idx",
            ),
            models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_outbox_lease_idx",
            ),
        ]

    def __str__(self):
        """Avoid exposing user IDs and other event metadata."""
        return f"Outbox event #{self.pk} ({self.status})"
