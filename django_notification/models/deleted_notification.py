from typing import Any, Tuple, List

from django.conf import settings
from django.db.models import Model, ForeignKey, CASCADE, DateTimeField, Index
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_notification.models.permissions.notification_permission import (
    NotificationPermission,
)
from django_notification.utils.user_model import get_username


class DeletedNotification(Model):
    """
    A model to track notifications that have been soft-deleted by users.

    This model is used to record when a notification was marked as deleted by a user.
    It provides a way to keep track of soft-deleted notifications for auditing or restoration purposes.

    Attributes:
        notification (ForeignKey): A foreign key to the Notification model representing the deleted notification.
        user (ForeignKey): A foreign key to the User model representing the user who deleted the notification.
        deleted_at (DateTimeField): A datetime field recording when the notification was deleted.

    Meta:
        db_table (str): The name of the database table.
        verbose_name (str): Human-readable singular name for the model.
        verbose_name_plural (str): Human-readable plural name for the model.
        unique_together (Tuple[str, str]): Ensures that each combination of user and notification is unique.

    Methods:
        __str__() -> str:
            Returns a string representation of the deleted notification including details of the notification and the user who deleted it.
        save(*args: Any, **kwargs: Any) -> None:
            Saves the object to the database after checking if the user has permission to delete the notification.
    """

    notification = ForeignKey(
        "Notification",
        verbose_name=_("Notification"),
        help_text=_("The notification that was deleted."),
        on_delete=CASCADE,
        related_name="deleted",
    )
    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        help_text=_("The user who deleted the notification."),
        on_delete=CASCADE,
        related_name="deleted_notifications",
    )
    deleted_at = DateTimeField(
        verbose_name=_("Deleted at"),
        help_text=_("The time when the notification was deleted."),
        default=timezone.now,
    )

    class Meta:
        db_table: str = "deleted_notifications"
        verbose_name: str = _("Deleted Notification")
        verbose_name_plural: str = _("Deleted Notifications")
        unique_together: Tuple[str, str] = ("user", "notification")
        indexes: List[Index] = [
            Index(
                fields=["notification", "user"],
                name="deleted_notification_user_idx",
            ),
        ]

    def __str__(self) -> str:
        """
        Return a string representation of the deleted notification.

        Returns:
            str: A string representation of the deleted notification including the notification and the user.
        """
        username = get_username(self.user)
        return f"{self.notification} deleted by {username} (ID: {self.user.pk})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Save the object to the database.

        This method first validates if the user has the necessary permission to delete the notification.
        If the user does not have permission, a PermissionError is raised.
         Otherwise, the object is saved to the database.

        Raises:
            PermissionError: If the user does not have permission to delete the notification.
        """

        permission_class = NotificationPermission(self)
        permission_class.validate_permission(self.user, "delete")

        super().save(*args, **kwargs)
