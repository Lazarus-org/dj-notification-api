"""Admin management for category policy and per-user preferences."""

from django.contrib import admin

from django_notification.models.notification_category import NotificationCategory
from django_notification.models.notification_preference import NotificationPreference
from django_notification.settings.conf import config


@admin.register(NotificationCategory, site=config.admin_site_class)
class NotificationCategoryAdmin(admin.ModelAdmin):
    """Manage category labels, status, and mandatory delivery policy."""

    list_display = ("slug", "name", "is_mandatory", "is_active")
    list_filter = ("is_mandatory", "is_active")
    search_fields = ("slug", "name")

    def get_readonly_fields(self, request, obj=None):
        """Prevent renaming keys that may already be referenced."""
        return ("slug",) if obj else ()


@admin.register(NotificationPreference, site=config.admin_site_class)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Inspect individual category opt-outs without exposing notification data."""

    list_display = ("category", "enabled", "updated_at")
    list_filter = ("category", "enabled")
    readonly_fields = ("updated_at",)
    raw_id_fields = ("user",)
