import sys

import pytest
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.db import IntegrityError
from django_notification.models import DeletedNotification, Notification
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.models,
    pytest.mark.models_deleted_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestDeletedNotification:
    """
    Test suite for the `DeletedNotification` model.
    """

    def test_string_representation(
        self, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test the string representation of a `DeletedNotification`.

        Asserts:
        -------
            - The string representation matches the expected format.
        """
        expected_str = (
            f"{deleted_notification.notification} deleted by"
            f" {deleted_notification.user} (ID: {deleted_notification.user.pk})"
        )
        assert str(deleted_notification) == expected_str

    def test_unique_together_constraint(self, notification: Notification, user: User) -> None:
        """
        Test that the combination of user and notification is unique.

        Asserts:
        -------
            - An `IntegrityError` is raised when attempting to create a duplicate entry.
        """
        notification.recipient.add(user)
        # Create the first DeletedNotification instance
        DeletedNotification.objects.create(
            notification=notification, user=user, deleted_at=now()
        )

        # Try to create a second DeletedNotification instance with the same notification and user
        with pytest.raises(IntegrityError):
            DeletedNotification.objects.create(
                notification=notification, user=user, deleted_at=now()
            )

    def test_save_method_with_valid_user(self, notification: Notification, user: User) -> None:
        """
        Test the save method when the user is a recipient or group member of the notification.

        Asserts:
        -------
            - The `DeletedNotification` instance is saved correctly if the user is a recipient or group member.
        """
        # Add the user as a recipient
        notification.recipient.add(user)

        # Save DeletedNotification instance
        deleted_notification = DeletedNotification(
            notification=notification, user=user, deleted_at=now()
        )
        deleted_notification.save()

        # Verify that the instance is saved
        assert DeletedNotification.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_save_method_with_invalid_user(self, notification: Notification, another_user: User) -> None:
        """
        Test that a `PermissionError` is raised when the user is not a recipient or group member.

        Asserts:
        -------
            - A `PermissionError` is raised with the appropriate message if the user is not authorized.
        """
        # Ensure that another_user is not a recipient or group member
        with pytest.raises(
            PermissionError,
            match="Sorry! you don't have permission to delete this notification",
        ):
            deleted_notification = DeletedNotification(
                notification=notification, user=another_user, deleted_at=now()
            )
            deleted_notification.save()

    def test_save_method_for_staff_user(self, notification: Notification, user: User) -> None:
        """
        Test that a staff user can save `DeletedNotification` even if they are not a recipient or group member.

        Asserts:
        -------
            - The `DeletedNotification` instance is saved correctly if the user is a staff member.
        """
        # Promote the user to staff
        user.is_staff = True
        user.save()

        # Save DeletedNotification instance
        deleted_notification = DeletedNotification(
            notification=notification, user=user, deleted_at=now()
        )
        deleted_notification.save()

        # Verify that the instance is saved
        assert DeletedNotification.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_default_field_values(
        self, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test default values for fields.

        Asserts:
        -------
            - The `deleted_at` field is not None.
        """
        assert deleted_notification.deleted_at is not None
