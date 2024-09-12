from typing import Tuple, List

from django.conf import settings
from django.db.models import Model, ForeignKey, CASCADE, Index
from django.utils.translation import gettext_lazy as _

from django_notification.utils.user_model import get_username


class NotificationRecipient(Model):
    """
    A model to represent the recipient of a notification.

    Attributes:
        notification (ForeignKey): A foreign key linking to the Notification model.
        recipient (ForeignKey): A foreign key linking to the User model.

    Meta:
        verbose_name (str): Human-readable singular name for the model.
        verbose_name_plural (str): Human-readable plural name for the model.
        unique_together (tuple): Ensures that a recipient cannot receive the same notification more than once.

    Methods:
        __str__() -> str:
            Returns a string representation of the notification recipient,
             including details of the associated notification and the recipient.
    """

    notification: ForeignKey["Notification"] = ForeignKey(
        "Notification",
        verbose_name=_("Notification"),
        help_text=_("The notification that is being sent."),
        on_delete=CASCADE,
        related_name="notification_recipients",
    )
    recipient: ForeignKey[settings.AUTH_USER_MODEL] = ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Recipient"),
        help_text=_("The user who will receive the notification."),
        on_delete=CASCADE,
        related_name="received_notifications",
    )

    class Meta:
        db_table: str = "notification_recipient"
        verbose_name: str = _("Notification Recipient")
        verbose_name_plural: str = _("Notification Recipients")
        unique_together: Tuple[str, str] = ("recipient", "notification")
        indexes: List[Index] = [
            Index(fields=["notification", "recipient"]),
        ]

    def __str__(self) -> str:
        """
        A string representation of the notification recipient.

        Returns:
            str: A string representation of the associated notification.
        """
        username = get_username(self.recipient)
        return f"Notification: {self.notification}, Recipient: {username} (ID: {self.recipient.pk})"
