"""Managed notification categories and their opt-out policy."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationCategory(models.Model):
    """A stable category key shared by notifications and user preferences.

    Deactivating a category prevents new managed notifications from using it; existing
    notifications keep their category and remain accessible.

    """

    slug = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120)
    is_mandatory = models.BooleanField(
        default=False,
        help_text=_("Mandatory categories cannot be disabled by users."),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_category"
        verbose_name = _("Notification category")
        verbose_name_plural = _("Notification categories")
        ordering = ("slug",)

    def __str__(self):
        """Display the category's human-readable name."""
        return self.name
