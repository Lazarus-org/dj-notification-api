"""Read-only administrative visibility into external delivery outcomes."""

from django.contrib import admin

from django_notification.models.notification_delivery import (
    NotificationDelivery,
    NotificationDeliveryAttempt,
)
from django_notification.settings.conf import config


class _ReadOnlyDeliveryAdmin(admin.ModelAdmin):
    """State is owned by the durable worker and recovery commands."""

    def has_add_permission(self, request):
        """Prevent manual, non-idempotent delivery creation."""
        return False

    def has_change_permission(self, request, obj=None):
        """Never mutate leases or attempts through the admin UI."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Preserve history until explicit retention handling."""
        return False


@admin.register(NotificationDelivery, site=config.admin_site_class)
class NotificationDeliveryAdmin(_ReadOnlyDeliveryAdmin):
    """Inspect per-channel status without displaying provider secrets."""

    list_display = (
        "id",
        "notification_id",
        "recipient_id",
        "channel",
        "status",
        "attempts",
        "created_at",
        "delivered_at",
    )
    list_filter = ("channel", "status")
    search_fields = ("=notification_id", "=recipient_id")
    ordering = ("-id",)


@admin.register(NotificationDeliveryAttempt, site=config.admin_site_class)
class NotificationDeliveryAttemptAdmin(_ReadOnlyDeliveryAdmin):
    """Inspect sanitized history, not backend exception messages."""

    list_display = ("id", "delivery_id", "number", "status", "code", "completed_at")
    list_filter = ("status", "code")
    search_fields = ("=delivery_id",)
    ordering = ("-id",)
