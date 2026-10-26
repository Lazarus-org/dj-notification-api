"""Per-user preferences for optional in-app notification categories."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationPreference(models.Model):
    """An explicit per-user override; absence means category is enabled.

    Preferences affect personal feed visibility, not record creation or the frozen
    membership of snapshot group audiences. Mandatory categories are always visible even
    if an old override row says otherwise.

    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    category = models.ForeignKey(
        "django_notification.NotificationCategory",
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preference"
        verbose_name = _("Notification preference")
        verbose_name_plural = _("Notification preferences")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "category"),
                name="unique_notification_preference_user_category",
            ),
        ]

    def __str__(self):
        """Describe the override without displaying user identifiers."""
        return f"{self.category_id}: {'on' if self.enabled else 'off'}"
