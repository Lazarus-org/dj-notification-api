from typing import Optional
from django.http import HttpRequest
from django.contrib.admin import ModelAdmin


class ReadOnlyAdminMixin:
    """
    A mixin that disables the ability to add, change, or delete objects in the Django admin.
    """

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Determines if the user has permission to add a new instance of the model.
        Returns False, meaning the user doesn't have permission to add.
        """
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Optional[ModelAdmin] = None
    ) -> bool:
        """
        Determines if the user has permission to change an existing instance of the model.
        Returns False, meaning the user doesn't have permission to change.
        """
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Optional[ModelAdmin] = None
    ) -> bool:
        """
        Determines if the user has permission to delete an existing instance of the model.
        Returns False, meaning the user doesn't have permission to delete.
        """
        return False
