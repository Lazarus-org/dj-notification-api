import sys

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from django_notification.models import Notification, NotificationRecipient
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.models,
    pytest.mark.models_notification_recipient,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationRecipient:
    """
    Test suite for the `NotificationRecipient` model.
    """

    def test_string_representation(
        self, notification_recipient: NotificationRecipient
    ) -> None:
        """
        Test the string representation of a `NotificationRecipient`.

        Asserts:
        -------
            - The string representation matches the expected format.
        """
        assert str(notification_recipient) == (
            f"Notification: {notification_recipient.notification}, "
            f"Recipient: {notification_recipient.recipient.username} (ID: {notification_recipient.recipient.pk})"
        )

    def test_unique_together_constraint(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test that the combination of recipient and notification is unique.

        Asserts:
        -------
            - An `IntegrityError` is raised when trying to create a duplicate `NotificationRecipient`.
        """
        # Create the first NotificationRecipient instance
        NotificationRecipient.objects.create(notification=notification, recipient=user)

        # Try to create a second NotificationRecipient instance with the same recipient and notification
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            NotificationRecipient.objects.create(
                notification=notification, recipient=user
            )
