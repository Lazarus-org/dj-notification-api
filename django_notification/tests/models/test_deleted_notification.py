import sys

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils.timezone import now

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

    def test_unique_together_constraint(
        self, notification: Notification, user: User
    ) -> None:
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

    def test_save_method_with_valid_user(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test the save method when the user is a direct recipient of the notification.

        Asserts:
        -------
            - The `DeletedNotification` instance is saved for a direct recipient.
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

    def test_group_member_can_soft_delete(
        self, notification: Notification, user: User, group
    ) -> None:
        """Targeted-group membership permits an independent soft-delete marker."""
        user.groups.add(group)
        notification.group.add(group)

        DeletedNotification.objects.create(notification=notification, user=user)

        assert DeletedNotification.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_save_method_with_invalid_user(
        self, notification: Notification, another_user: User
    ) -> None:
        """
        Test that a `PermissionError` is raised when the user is not a direct recipient.

        Asserts:
        -------
            - A `PermissionError` is raised with the appropriate message if the user is not authorized.
        """
        # Ensure that another_user is not a direct recipient.
        with pytest.raises(
            PermissionError,
            match="Sorry! you don't have permission to delete this notification",
        ):
            deleted_notification = DeletedNotification(
                notification=notification, user=another_user, deleted_at=now()
            )
            deleted_notification.save()

    def test_save_method_for_staff_non_recipient_is_denied(
        self, notification: Notification, user: User
    ) -> None:
        """Staff status alone does not grant soft-delete ownership."""
        user.is_staff = True
        user.save()

        with pytest.raises(
            PermissionError,
            match="Sorry! you don't have permission to delete this notification",
        ):
            DeletedNotification.objects.create(notification=notification, user=user)

        assert not DeletedNotification.objects.filter(
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
