import sys

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils.timezone import now

from django_notification.models import Notification, NotificationSeen
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.models,
    pytest.mark.models_notification_seen,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationSeen:
    """
    Test suite for the `NotificationSeen` model.
    """

    def test_string_representation(self, notification_seen: NotificationSeen) -> None:
        """
        Test the string representation of a `NotificationSeen`.

        Asserts:
        -------
            - The string representation matches the expected format.
        """
        expected_str = f"{notification_seen.user} (ID: {notification_seen.user.pk}) has seen ({notification_seen.notification})"
        assert str(notification_seen) == expected_str

    def test_unique_together_constraint(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test that the combination of notification and user is unique.

        Asserts:
        -------
            - An `IntegrityError` is raised when trying to create a duplicate `NotificationSeen`.
        """
        notification.recipient.add(user)
        # Create the first NotificationSeen instance
        NotificationSeen.objects.create(
            notification=notification, user=user, seen_at=now()
        )

        # Try to create a second NotificationSeen instance with the same notification and user
        with pytest.raises(IntegrityError):
            NotificationSeen.objects.create(
                notification=notification, user=user, seen_at=now()
            )

    def test_save_method_with_valid_user(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test the save method when the user is a direct recipient of the notification.

        Asserts:
        -------
            - The `NotificationSeen` instance is saved successfully for a direct
              recipient.
        """
        # Add the user as a recipient
        notification.recipient.add(user)

        # Save NotificationSeen instance
        notification_seen = NotificationSeen(
            notification=notification, user=user, seen_at=now()
        )
        notification_seen.save()

        # Verify that the instance is saved
        assert NotificationSeen.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_group_member_can_mark_seen(
        self, notification: Notification, user: User, group
    ) -> None:
        """Targeted-group membership permits an individual seen marker."""
        user.groups.add(group)
        notification.group.add(group)

        NotificationSeen.objects.create(notification=notification, user=user)

        assert NotificationSeen.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_save_method_with_invalid_user(
        self, notification: Notification, another_user: User
    ) -> None:
        """
        Test that a `PermissionError` is raised when the user is not a direct recipient.

        Asserts:
        -------
            - A `PermissionError` is raised with the expected message.
        """
        # Ensure that another_user is not a direct recipient.
        with pytest.raises(
            PermissionError,
            match="Sorry! you don't have permission to mark as seen this notification.",
        ):
            notification_seen = NotificationSeen(
                notification=notification, user=another_user, seen_at=now()
            )
            notification_seen.save()

    def test_save_method_for_staff_non_recipient_is_denied(
        self, notification: Notification, user: User
    ) -> None:
        """Staff status alone does not grant read-state ownership."""
        user.is_staff = True
        user.save()

        with pytest.raises(
            PermissionError,
            match="Sorry! you don't have permission to mark as seen this notification.",
        ):
            NotificationSeen.objects.create(notification=notification, user=user)

        assert not NotificationSeen.objects.filter(
            notification=notification, user=user
        ).exists()

    def test_default_field_values(self, notification_seen: NotificationSeen) -> None:
        """
        Test default values for fields.

        Asserts:
        -------
            - The `seen_at` field is not None.
        """
        assert notification_seen.seen_at is not None
