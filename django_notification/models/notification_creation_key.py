"""Database-backed keys for reliable, retry-safe notification creation."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class CreationKeyKind(models.TextChoices):
    """Persistent retry identity versus time-bounded event coalescing."""

    IDEMPOTENCY = "IDEMPOTENCY", _("Idempotent creation")
    DEDUPLICATION = "DEDUPLICATION", _("Time-window deduplication")


class NotificationCreationKey(models.Model):
    """Serialized database claim for one logical notification creation event.

    Keys are application-owned, never accepted from the self-service HTTP API. Rows are
    transactionally assigned to a Notification; a hard delete cascades to its keys, so
    retry guarantees apply while that Notification exists.

    """

    kind = models.CharField(max_length=13, choices=CreationKeyKind.choices)
    key = models.CharField(max_length=200)
    notification = models.ForeignKey(
        "django_notification.Notification",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="creation_keys",
    )
    request_fingerprint = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "notification_creation_key"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "key"], name="unique_notification_creation_key"
            ),
        ]

    def __str__(self):
        """Return a non-sensitive representation without exposing the key."""
        return f"{self.kind}: notification #{self.notification_id}"
