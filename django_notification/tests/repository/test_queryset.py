import sys
from typing import List

import pytest
from django.contrib.auth.models import User, Group

from django_notification.models import Notification, DeletedNotification
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.queryset,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationQuerySet:
    """
    Test suite for the `NotificationQuerySet`.
    """

    def test_all_notifications_with_recipients(
        self, notifications: List[Notification], qs_user: List[User]
    ) -> None:
        """
        Test that `all_notifications` filters notifications by recipients.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to filter notifications by.

        Asserts:
        -------
            The count of notifications returned by `all_notifications` with the given recipients
            matches the number of provided notifications.
        """
        queryset = Notification.queryset.all_notifications(recipients=qs_user)
        assert queryset.count() == len(notifications)

    def test_all_notifications_with_groups(
        self, notifications: List[Notification], qs_group: List[Group]
    ) -> None:
        """
        Test that `all_notifications` filters notifications by groups.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_group (List[Group]): List of group instances to filter notifications by.

        Asserts:
        -------
            The count of notifications returned by `all_notifications` with the given groups
            matches the number of provided notifications.
        """
        queryset = Notification.queryset.all_notifications(groups=qs_group)
        assert queryset.count() == len(notifications)

    def test_all_notifications_with_recipients_and_groups(
        self,
        notifications: List[Notification],
        qs_user: List[User],
        qs_group: List[Group],
    ) -> None:
        """
        Test that `all_notifications` filters notifications by both recipients and groups.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to filter notifications by.
            qs_group (List[Group]): List of group instances to filter notifications by.

        Asserts:
        -------
            The count of notifications returned by `all_notifications` with the given recipients
            and groups matches the number of provided notifications.
        """
        queryset = Notification.queryset.all_notifications(
            recipients=qs_user, groups=qs_group
        )
        assert queryset.count() == len(notifications)

    def test_sent_with_groups(
        self, notifications: List[Notification], qs_group: List[Group]
    ) -> None:
        """
        Test that `sent` filters notifications by groups.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_group (List[Group]): List of group instances to filter sent notifications by.

        Asserts:
        -------
            The count of notifications returned by `sent` with the given groups matches the number
            of notifications that have been marked as sent.
        """
        queryset = Notification.queryset.sent(groups=qs_group)
        assert queryset.count() == len([n for n in notifications if n.is_sent])

    def test_unsent(self, notifications: List[Notification]) -> None:
        """
        Test that `unsent` filters only unsent notifications.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.

        Asserts:
        -------
            The count of notifications returned by `unsent` matches the number of notifications
            that have not been marked as sent.
        """
        queryset = Notification.queryset.unsent()
        assert queryset.count() == len([n for n in notifications if not n.is_sent])

    def test_unsent_with_recipients_and_groups(
        self,
        notifications: List[Notification],
        qs_user: List[User],
        qs_group: List[Group],
    ) -> None:
        """
        Test that `unsent` filters unsent notifications with recipients and groups.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to filter unsent notifications by.
            qs_group (List[Group]): List of group instances to filter unsent notifications by.

        Asserts:
        -------
            The count of notifications returned by `unsent` with the given recipients and groups
            matches the number of unsent notifications.
        """
        queryset = Notification.queryset.unsent(recipients=qs_user, groups=qs_group)
        assert queryset.count() == len([n for n in notifications if not n.is_sent])

    def test_unsent_exclude_deleted(
        self, notifications: List[Notification], qs_user: List[User]
    ) -> None:
        """
        Test that `unsent` excludes notifications that have been soft deleted.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to exclude deleted notifications by.

        Asserts:
        -------
            The count of notifications returned by `unsent` with excluded deleted notifications
            is greater than 0.
        """
        queryset = Notification.queryset.unsent(exclude_deleted_by=qs_user)
        assert queryset.count() > 0

    def test_mark_as_sent(self, notifications: List[Notification]) -> None:
        """
        Test that `mark_as_sent` is called for all notifications.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.

        Asserts:
        -------
            The `mark_as_sent` method is successfully called. (Placeholder assertion)
        """
        Notification.queryset.mark_all_as_sent()
        assert True

    def test_deleted(
        self, notifications: List[Notification], qs_user: List[User]
    ) -> None:
        """
        Test that `deleted` returns notifications that have been marked as deleted.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to filter deleted notifications by.

        Asserts:
        -------
            The count of notifications returned by `deleted` is 0, indicating no notifications
            are marked as deleted yet.
        """
        deleted = Notification.queryset.deleted(deleted_by=qs_user)
        assert deleted.count() == 0  # Assuming no notifications are deleted yet

    def test_create_notification_with_groups(
        self, another_user: User, qs_user: List[User], qs_group: List[Group]
    ) -> None:
        """
        Test that `create_notification` adds groups correctly to the notification.

        Args:
        ----
            another_user (User): User instance acting as the notification actor.
            qs_user (List[User]): List of user instances to be recipients of the notification.
            qs_group (List[Group]): List of group instances to be added to the notification.

        Asserts:
        -------
            The created notification should have the specified groups.
        """
        notification = Notification.queryset.create_notification(
            verb="Test",
            actor=another_user,
            recipients=qs_user,
            groups=qs_group,
            status="INFO",
        )
        assert notification.group.count() == 1
        assert notification.group.first() == qs_group

    def test_update_notification(self, notifications: List[Notification]) -> None:
        """
        Test that `update_notification` correctly updates the notification attributes.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.

        Asserts:
        -------
            The updated notification should have the new attributes applied.
        """
        notification = notifications[1]
        updated_notification = Notification.queryset.update_notification(
            notification_id=notification.id,
            is_sent=True,
            public=False,
            data={"key": "value"}
        )
        assert updated_notification.is_sent is True
        assert updated_notification.public is False
        assert updated_notification.data is not None

    def test_delete_notification_without_recipient(
        self, notifications: List[Notification]
    ) -> None:
        """
        Test that `delete_notification` raises a ValueError if no recipient is provided for a soft delete.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.

        Asserts:
        -------
            A ValueError should be raised if no recipient is provided for the delete operation.
        """
        notification = notifications[0]
        with pytest.raises(ValueError):
            Notification.queryset.delete_notification(
                notification_id=notification.id, recipient=None, soft_delete=True
            )

    def test_delete_notification_with_recipient(
        self, notifications: List[Notification], qs_user: List[User]
    ) -> None:
        """
        Test that `delete_notification` correctly handles soft delete with a recipient.

        Args:
        ----
            notifications (List[Notification]): List of notification instances for testing.
            qs_user (List[User]): List of user instances to be used for the soft delete operation.

        Asserts:
        -------
            The deleted notification should exist in the DeletedNotification model.
        """
        notification = notifications[2]
        Notification.queryset.delete_notification(
            notification_id=notification.id, recipient=qs_user, soft_delete=True
        )
        assert DeletedNotification.objects.filter(
            notification=notification, user=qs_user
        ).exists()
