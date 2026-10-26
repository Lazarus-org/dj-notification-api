"""Schedule configuration and read-only digest operational visibility."""

from django.contrib import admin

from django_notification.models.notification_delivery_schedule import (
    NotificationDeliverySchedule,
)
from django_notification.models.notification_digest import NotificationDigest
from django_notification.settings.conf import config

from .delivery import _ReadOnlyDeliveryAdmin


@admin.register(NotificationDeliverySchedule, site=config.admin_site_class)
class NotificationDeliveryScheduleAdmin(admin.ModelAdmin):
    """Per-user schedules; model.full_clean validates IANA zone settings."""

    list_display = (
        "id",
        "channel",
        "frequency",
        "timezone",
        "quiet_start",
        "quiet_end",
    )
    list_filter = ("channel", "frequency")
    raw_id_fields = ("user",)


@admin.register(NotificationDigest, site=config.admin_site_class)
class NotificationDigestAdmin(_ReadOnlyDeliveryAdmin):
    """View lease and delivery state; recovery uses a management command."""

    list_display = (
        "id",
        "recipient_id",
        "channel",
        "scheduled_at",
        "status",
        "attempts",
        "delivered_at",
    )
    list_filter = ("channel", "status")
    search_fields = ("=recipient_id",)
    ordering = ("-id",)
