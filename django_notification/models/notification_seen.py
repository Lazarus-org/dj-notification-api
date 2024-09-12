from typing import Any, Tuple, List

from django.core.exceptions import ValidationError
from django.db.models import Model, ForeignKey, DateTimeField, CASCADE, Index
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_notification.models.permissions.notification_permission import (
    NotificationPermission,
)
from django_notification.utils.user_model import get_username


class NotificationSeen(Model):
    """
    A model that tracks when a user has seen a specific notification.

    Attributes:
        notification (ForeignKey): A foreign key linking to the Notification model,
            indicating which notification was seen.
        user (ForeignKey): A foreign key linking to the User model,
            representing the recipient or group member who has seen the notification.
        seen_at (DateTimeField): A timestamp of when the notification was seen,
            automatically set to the current time when created.

    Meta:
        db_table (str): The name of the database table (`notification_seen`).
        verbose_name (str): A human-readable singular name for the model ("Notification Seen").
        verbose_name_plural (str): A human-readable plural name for the model ("Notifications Seen").
        unique_together (tuple): Ensures that a user cannot mark the same notification as seen more than once.
        indexes (list): Database indexes for fast querying by notification and user.
        ordering (tuple): Orders records by `seen_at` in descending order.

    Methods:
        __str__() -> str:
            Returns a string representation of the model, including the user's username and notification details.
        save(*args, **kwargs) -> None:
            Saves the instance to the database.
            - Validates that the `seen_at` timestamp is not in the past.
            - Ensures the user has permission to mark the notification as seen.
            - If the user does not have permission, raises a `PermissionError`.

    Usage Example:
        After a user views a notification, create a `NotificationSeen` instance to track that event:
            seen_instance = NotificationSeen(notification=notif, user=user)
            seen_instance.save()

        The `seen_at` field is automatically populated with the current time, and you can query
        when a specific user saw a notification or how many users have seen it.
    """

    notification = ForeignKey(
        "Notification",
        verbose_name=_("Notification"),
        help_text=_("The notification that was seen."),
        on_delete=CASCADE,
        related_name="seen",
    )
    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        help_text=_("The recipient or a group member who has seen the notification."),
        on_delete=CASCADE,
        related_name="seen_notifications",
    )
    seen_at = DateTimeField(
        verbose_name=_("Seen at"),
        help_text=_("The time that the notification was seen."),
        default=timezone.now,
    )

    class Meta:
        db_table: str = "notification_seen"
        verbose_name: str = _("Notification Seen")
        verbose_name_plural: str = _("Notifications Seen")
        unique_together: Tuple[str, str] = ("notification", "user")
        indexes: List[Index] = [
            Index(fields=["notification", "user"]),
        ]
        ordering: Tuple[str] = ("-seen_at",)

    def __str__(self) -> str:
        username = get_username(self.user)
        return f"{username} (ID: {self.user.pk}) has seen ({self.notification})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Saves the object to the database.

        This method checks if the user has permission to mark the notification as seen and
        validates that the `seen_at` time is not in the past.

        Args:
            *args: Additional positional arguments passed to the parent `save` method.
            **kwargs: Additional keyword arguments passed to the parent `save` method.

        Raises:
            PermissionError: If the user does not have permission to mark the notification as seen.
            ValidationError: If the `seen_at` time is in the past.

        Returns:
            None
        """
        permission_class = NotificationPermission(self)
        permission_class.validate_permission(self.user, "mark as seen")

        # Validate that seen_at is not in the past for the initial save
        if not self.pk and self.seen_at and self.seen_at < timezone.now():
            raise ValidationError("The 'seen_at' time cannot be in the past.")

        super().save(*args, **kwargs)
