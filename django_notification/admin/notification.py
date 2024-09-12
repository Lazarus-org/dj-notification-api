from django.contrib import admin

from django_notification.mixins import ReadOnlyAdminMixin
from django_notification.models.notification import (
    Notification,
    NotificationRecipient,
    NotificationSeen,
)
from django_notification.utils.user_model import USERNAME_FIELD


class NotificationRecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0

    def get_queryset(self, request):
        """
        Override the get_queryset method to select related fields for performance optimization.
        """
        return super().get_queryset(request).select_related("notification", "recipient")


class NotificationSeenInline(admin.TabularInline):
    model = NotificationSeen
    extra = 0

    def get_queryset(self, request):
        """
        Override the get_queryset method to select related fields for performance optimization.
        """
        return super().get_queryset(request).select_related("notification", "user")


@admin.register(Notification)
class NotificationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    actions = ["mark_as_sent"]
    inlines = [NotificationRecipientInline, NotificationSeenInline]
    list_display = ["id", "get_title", "is_sent", "public", "timestamp"]
    list_filter = ["is_sent", "public", "timestamp"]
    list_per_page = 10
    search_fields = ["id", f"recipient__{USERNAME_FIELD}", "group__name"]

    def get_title(self, instance):
        return str(instance)

    get_title.short_description = "Title"

    def get_queryset(self, request):
        """
        Override the get_queryset method to select related fields for performance optimization.
        """
        return (
            super()
            .get_queryset(request)
            .select_related(
                "actor_content_type",
                "target_content_type",
                "action_object_content_type",
            )
        )

    # Admin action to mark selected notifications as sent
    def mark_as_sent(self, request, queryset):
        updated = queryset.update(is_sent=True)
        self.message_user(
            request,
            f"{updated} notification(s) successfully marked as sent."
        )
