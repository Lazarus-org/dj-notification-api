import logging

from django_notification.utils.user_model import UserModel


class NotificationPermission:
    """A permission class responsible for determining if a user has permission to
    perform actions related to notifications.

    This class encapsulates the permission logic for notifications, allowing
    for a clear separation of concerns and making it reusable across the system.

    Attributes:
        notification (Notification): The notification object to check permissions for.

    Methods:
        user_has_permission(user: User) -> bool:
            Checks for direct-recipient or targeted-group membership.
        validate_permission(user: User, action: str) -> None:
            Validates whether the user can perform an action on the notification.

    """

    def __init__(self, notification):
        self.notification = notification

    def user_has_permission(self, user: UserModel) -> bool:
        """Check whether the user is a direct recipient or group member.

        Args:
            user (User): The user to check.

        Returns:
            bool: Whether the user has permission or not.

        """
        notification = self.notification
        if notification.pk is None:
            return False

        # Use the same authoritative direct/group visibility policy as the API
        # and lifecycle service. This also handles inactive/anonymous users and
        # custom user models without a `groups` relationship.
        queryset = notification.__class__.objects
        if notification._state.db is not None:
            queryset = queryset.db_manager(notification._state.db)
        return queryset.visible_to(user).active_at().filter(pk=notification.pk).exists()

    def validate_permission(self, user: UserModel, action: str) -> None:
        """Validate if the user has permission to perform a specific action on the
        notification.

        Args:
            user (User): The user to validate.
            action (str): The action to be performed ('seen', 'save', 'delete').

        Raises:
            PermissionError: If the user does not have permission.

        """
        if not self.user_has_permission(user):
            logging.warning("Notification permission denied for action: %s", action)
            raise PermissionError(
                f"Sorry! you don't have permission to {action} this notification."
            )
