from typing import Optional
from django.http import HttpRequest
from django.contrib.admin import ModelAdmin

from django_notification.settings.conf import config


class ReadOnlyAdminMixin:
    """
    A mixin that manages the ability to add, change, or delete objects in the Django admin.
    """

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Determines if the user has permission to add a new instance of the model.
        """
        return config.admin_has_add_permission

    def has_change_permission(
        self, request: HttpRequest, obj: Optional[ModelAdmin] = None
    ) -> bool:
        """
        Determines if the user has permission to change an existing instance of the model.
        """
        return config.admin_has_change_permission

    def has_delete_permission(
        self, request: HttpRequest, obj: Optional[ModelAdmin] = None
    ) -> bool:
        """
        Determines if the user has permission to delete an existing instance of the model.
        """
        return config.admin_has_delete_permission
