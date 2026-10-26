"""Severity-independent delivery/display priority levels."""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class NotificationPriority(TextChoices):
    """Order-independent priority labels, distinct from notification status."""

    LOW = "LOW", _("Low")
    NORMAL = "NORMAL", _("Normal")
    HIGH = "HIGH", _("High")
    URGENT = "URGENT", _("Urgent")
