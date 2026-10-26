"""Admin-only configuration of external notification routing rules."""

from django.contrib import admin

from django_notification.models.notification_routing_rule import NotificationRoutingRule
from django_notification.settings.conf import config


@admin.register(NotificationRoutingRule, site=config.admin_site_class)
class NotificationRoutingRuleAdmin(admin.ModelAdmin):
    """Manage channel rules without exposing user records or payloads."""

    list_display = (
        "name",
        "category",
        "sort_order",
        "min_priority",
        "max_priority",
        "notification_status",
        "action",
        "enabled",
    )
    list_filter = ("enabled", "action", "category", "min_priority")
    search_fields = ("name",)
    ordering = ("sort_order", "pk")
