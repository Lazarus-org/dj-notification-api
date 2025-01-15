from typing import Any, List

from django.contrib import admin
from django.db.models import Field, QuerySet, URLField
from django.forms import Field as FormField
from django.http import HttpRequest

from django_notification.mixins import ReadOnlyAdminMixin
from django_notification.models.notification import (
    Notification,
    NotificationRecipient,
    NotificationSeen,
)
from django_notification.settings.conf import config
from django_notification.utils.user_model import USERNAME_FIELD


class NotificationRecipientInline(admin.TabularInline):
    """Inline admin interface for NotificationRecipient model.

    Attributes:
        model: The model associated with this inline.
        extra: Number of empty forms to display.

    """

    model = NotificationRecipient
    extra = 0

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Override the get_queryset method to select related fields for
        performance optimization.

        Args:
            request: The current HTTP request.

        Returns:
            A queryset with selected related fields for performance optimization.

        """
        return super().get_queryset(request).select_related("notification", "recipient")


class NotificationSeenInline(admin.TabularInline):
    """Inline admin interface for NotificationSeen model.

    Attributes:
        model: The model associated with this inline.
        extra: Number of empty forms to display.

    """

    model = NotificationSeen
    extra = 0

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Override the get_queryset method to select related fields for
        performance optimization.

        Args:
            request: The current HTTP request.

        Returns:
            A queryset with selected related fields for performance optimization.

        """
        return super().get_queryset(request).select_related("notification", "user")


@admin.register(Notification, site=config.admin_site_class)
class NotificationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Admin interface for managing Notification model.

    Attributes:
        actions: List of actions available for the admin.
        inlines: List of inline admin interfaces associated with this model.
        list_display: Fields to display in the list view.
        list_filter: Fields to filter the list view.
        list_per_page: Number of items per page in the list view.
        search_fields: Fields to search through in the list view.

    """

    actions: List[str] = ["mark_as_sent"]
    inlines: List[admin.TabularInline] = [
        NotificationRecipientInline,
        NotificationSeenInline,
    ]
    list_display: List[str] = ["id", "get_title", "is_sent", "public", "timestamp"]
    list_filter: List[str] = ["is_sent", "public", "timestamp"]
    list_per_page: int = 10
    search_fields: List[str] = ["id", f"recipient__{USERNAME_FIELD}", "group__name"]

    def get_title(self, instance: Notification) -> str:
        """Retrieve the title of the notification for display in the list view.

        Args:
            instance: The Notification instance being displayed.

        Returns:
            A string representation of the notification.

        """
        return str(instance)

    get_title.short_description = "Title"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Override the get_queryset method to select related fields for
        performance optimization.

        Args:
            request: The current HTTP request.

        Returns:
            A queryset with selected related fields for performance optimization.

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

    def mark_as_sent(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Admin action to mark selected notifications as sent.

        Args:
            request: The current HTTP request.
            queryset: The queryset of selected notifications.

        """
        updated = queryset.update(is_sent=True)
        self.message_user(
            request, f"{updated} notification(s) successfully marked as sent."
        )

    def formfield_for_dbfield(
        self, db_field: Field, request: HttpRequest, **kwargs: Any
    ) -> FormField:
        """Customize the form field for database fields in the admin interface.

        This method ensures that URLFields default to the HTTPS scheme when
        a scheme is not provided.

        Args:
            db_field: The model field to create a form field for.
            request: The current HTTP request object.
            **kwargs: Additional keyword arguments for form field configuration.

        Returns:
            The form field instance configured for the specified database field.

        """
        import django

        if isinstance(db_field, URLField) and django.VERSION >= (
            5,
            0,
        ):  # pragma: no cover
            kwargs["assume_scheme"] = "https"
        return super().formfield_for_dbfield(db_field, request, **kwargs)
