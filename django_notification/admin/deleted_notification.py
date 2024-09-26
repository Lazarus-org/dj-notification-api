from typing import List, Tuple

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from django_notification.mixins import ReadOnlyAdminMixin
from django_notification.models.deleted_notification import DeletedNotification
from django_notification.settings.conf import config
from django_notification.utils.user_model import USERNAME_FIELD


@admin.register(DeletedNotification, site=config.admin_site_class)
class DeletedNotificationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Admin interface for managing DeletedNotification model.

    Attributes:
        autocomplete_fields: Fields that use autocomplete functionality.
        list_display: Fields to display in the list view.
        list_filter: Fields to filter the list view.
        list_per_page: Number of items per page in the list view.
        search_fields: Fields to search through in the list view.

    """

    autocomplete_fields: List[str] = ["notification", "user"]
    list_display: List[str] = [
        "notification_id",
        "get_title",
        "get_deleted_by",
        "deleted_at",
    ]
    list_filter: List[str] = ["deleted_at"]
    list_per_page: int = 10
    search_fields: List[str] = ["notification__id", f"user__{USERNAME_FIELD}"]

    def get_search_results(
        self, request: HttpRequest, queryset: QuerySet, search_term: str
    ) -> Tuple[QuerySet, bool]:
        """Override the get_search_results method to include additional search
        logic.

        Searches by notification ID or user details. Adds results to the queryset if the search term is valid.

        Args:
            request: The current request object.
            queryset: The current queryset to filter.
            search_term: The search term to filter by.

        Returns:
            A tuple containing the filtered queryset and a boolean indicating if DISTINCT should be used.

        """
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        try:
            # Check if search term is an integer to search by notification ID
            search_term_int = int(search_term)
            queryset |= self.model.objects.filter(notification__id=search_term_int)
        except ValueError:
            # Dynamically filter using the USERNAME_FIELD
            filter_kwargs = {f"user__{USERNAME_FIELD}__icontains": search_term}
            queryset |= self.model.objects.filter(**filter_kwargs)

        return queryset, use_distinct

    def get_title(self, instance: DeletedNotification) -> str:
        """Retrieve the title of the notification for display in the list view.

        Args:
            instance: The DeletedNotification instance being displayed.

        Returns:
            A string representation of the notification.

        """
        return str(instance.notification)

    get_title.short_description = "Title"

    def get_deleted_by(self, instance: DeletedNotification) -> str:
        """Retrieve the username of the user who deleted the notification.

        Args:
            instance: The DeletedNotification instance being displayed.

        Returns:
            The username of the user who deleted the notification.

        """
        return str(instance.user)

    get_deleted_by.short_description = "Deleted by"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Override the get_queryset method to select related fields for
        performance optimization.

        Args:
            request: The current request object.

        Returns:
            The queryset with selected related fields.

        """
        return super().get_queryset(request).select_related("notification", "user")
