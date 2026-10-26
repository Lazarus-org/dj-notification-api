"""Manage external delivery templates and inspect user channel overrides."""

from django.contrib import admin

from django_notification.models.notification_channel_preference import (
    NotificationChannelPreference,
)
from django_notification.models.notification_template import NotificationTemplate
from django_notification.settings.conf import config


@admin.register(NotificationTemplate, site=config.admin_site_class)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Editable category/channel/locale templates with strict field validation."""

    list_display = ("category", "channel", "locale", "is_active")
    list_filter = ("channel", "is_active", "locale")
    search_fields = ("category__slug", "locale")


@admin.register(NotificationChannelPreference, site=config.admin_site_class)
class NotificationChannelPreferenceAdmin(admin.ModelAdmin):
    """Inspect overrides; UI users manage them via authenticated REST."""

    list_display = ("category", "channel", "enabled", "updated_at")
    list_filter = ("category", "channel", "enabled")
    raw_id_fields = ("user",)
    readonly_fields = ("updated_at",)
