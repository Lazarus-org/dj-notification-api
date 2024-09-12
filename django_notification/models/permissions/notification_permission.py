from django.contrib.auth.models import User
import logging


class NotificationPermission:
    """
    A permission class responsible for determining if a user has permission
    to perform actions related to notifications.

    This class encapsulates the permission logic for notifications, allowing
    for a clear separation of concerns and making it reusable across the system.

    Attributes:
        notification (Notification): The notification object to check permissions for.

    Methods:
        user_has_permission(user: User) -> bool:
            Checks if the user is a recipient, in a group, or a staff member with permission.
        validate_permission(user: User, action: str) -> None:
            Validates if the user has permission to perform a specific action on the notification.
    """

    def __init__(self, notification):
        self.notification = notification

    def user_has_permission(self, user: User) -> bool:
        """
        Check if the user is a recipient, in a group, or a staff member with permission.

        Args:
            user (User): The user to check.

        Returns:
            bool: Whether the user has permission or not.
        """
        is_recipient = self.notification.recipient.filter(pk=user.pk).exists()
        is_in_group = self.notification.group.filter(
            pk__in=user.groups.values_list("id", flat=True)
        ).exists()

        return is_recipient or is_in_group or user.is_staff

    def validate_permission(self, user: User, action: str) -> None:
        """
        Validate if the user has permission to perform a specific action on the notification.

        Args:
            user (User): The user to validate.
            action (str): The action to be performed ('seen', 'save', 'delete').

        Raises:
            PermissionError: If the user does not have permission.
        """
        if not self.user_has_permission(user):
            username = getattr(user, user.USERNAME_FIELD, "Unknown")
            logging.warning(
                "User %s (ID: %s) tried to %s notification %s without permission.",
                username,
                user.pk,
                action,
                self.notification.pk,
            )
            raise PermissionError(
                f"Sorry! you don't have permission to {action} this notification."
            )
