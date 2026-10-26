"""Operator-managed delivery routing for a category, priority and status."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.models.helper.enums.status_choices import NotificationStatus
from django_notification.models.notification_channel_preference import CHANNEL_VALUES


class RoutingAction(models.TextChoices):
    """Deterministic set operations over configured external channels."""

    REPLACE = "REPLACE", _("Use only these channels")
    ADD = "ADD", _("Add these channels")
    REMOVE = "REMOVE", _("Remove these channels")


PRIORITY_LEVELS = tuple(item.value for item in NotificationPriority)
PRIORITY_RANK = {value: rank for rank, value in enumerate(PRIORITY_LEVELS)}


class NotificationRoutingRule(models.Model):
    """Apply channel choices at queue time and before each external send.

    A null category is global. Rules are ordered by (sort_order, global before category-
    specific, id). They never override a user's channel opt-out or enable a backend that
    the application has not configured.

    """

    category = models.ForeignKey(
        "django_notification.NotificationCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="routing_rules",
    )
    name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    min_priority = models.CharField(
        max_length=8,
        choices=NotificationPriority.choices,
        default=NotificationPriority.LOW,
    )
    max_priority = models.CharField(
        max_length=8,
        choices=NotificationPriority.choices,
        default=NotificationPriority.URGENT,
    )
    notification_status = models.CharField(
        max_length=15,
        choices=NotificationStatus.choices,
        null=True,
        blank=True,
        help_text=_("Leave empty to match any notification status."),
    )
    action = models.CharField(max_length=7, choices=RoutingAction.choices)
    channels = models.JSONField(default=list)

    class Meta:
        db_table = "notification_routing_rule"
        ordering = ("sort_order", "pk")
        indexes = [
            models.Index(
                fields=("enabled", "category", "sort_order"),
                name="djnotify_routing_lookup_idx",
            ),
        ]

    def clean(self):
        """Reject invalid or ambiguous actions before configuration is saved."""
        super().clean()
        errors = {}
        lower = PRIORITY_RANK.get(self.min_priority)
        upper = PRIORITY_RANK.get(self.max_priority)
        if lower is None or upper is None or lower > upper:
            errors["max_priority"] = _("Invalid priority range.")
        if self.notification_status and self.notification_status not in {
            entry.value for entry in NotificationStatus
        }:
            errors["notification_status"] = _("Unknown status.")
        if self.action not in RoutingAction.values:
            errors["action"] = _("Unknown routing action.")
        if (
            not isinstance(self.channels, list)
            or not self.channels
            or any(not isinstance(value, str) for value in self.channels)
            or len(self.channels) != len(set(self.channels))
            or not set(self.channels) <= CHANNEL_VALUES
        ):
            errors["channels"] = _(
                "Provide a nonempty list of unique, supported channels."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Enforce safe configuration for ordinary programmatic writes."""
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        """Expose configuration names, never recipient identifiers."""
        return self.name
