import sys
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.models import DeletedNotification, NotificationSeen
from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_views,
    pytest.mark.api_views_activity,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestActivityViewSet:
    """
    Test suite for the ActivityViewSet class.

    This class includes tests for various actions and methods provided by the
    ActivityViewSet. It checks functionality such as retrieval of notifications,
    and clearing or deleting activities based on user roles and configuration settings.
    """

    def setup_method(self) -> None:
        """
        Setup the test client and create test data before each test.
        """
        self.client = APIClient()

    def test_staff_activity_list_is_scoped_to_direct_recipients(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        """Staff status must not expose another user's seen notification."""
        notification.recipient.add(user)
        notification.seen_by.add(user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("activities-list"))

        assert response.status_code == 200
        assert notification.pk not in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_staff_can_list_own_seen_notification(
        self, admin_user: User, notification: Notification
    ) -> None:
        notification.recipient.add(admin_user)
        notification.seen_by.add(admin_user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("activities-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_activity_list_contains_directly_addressed_seen_notifications(
        self, user: User, notification: Notification
    ) -> None:
        notification.recipient.add(user)
        notification.seen_by.add(user)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("activities-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_group_only_seen_record_is_visible_to_member(
        self, user: User, group
    ) -> None:
        """A group member can see their own group-notification activity."""
        user.groups.add(group)
        notification = Notification.objects.create_notification(
            verb="group notice",
            actor=user,
            description="A group-only notification",
            is_sent=True,
        )
        notification.group.add(group)
        # Simulate a read-state row created before the authorization hardening.
        NotificationSeen.objects.bulk_create(
            [NotificationSeen(notification=notification, user=user)]
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("activities-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_group_member_can_view_and_clear_own_activity(
        self,
        user: User,
        another_user: User,
        group,
        notification: Notification,
    ) -> None:
        """One member's read/clear state does not change other members' feeds."""
        user.groups.add(group)
        another_user.groups.add(group)
        notification.group.add(group)
        notification.mark_as_seen(user)
        self.client.force_authenticate(user=user)

        listing = self.client.get(reverse("activities-list"))
        detail = self.client.get(
            reverse("activities-detail", kwargs={"pk": notification.pk})
        )
        cleared = self.client.get(
            reverse("activities-clear-notification", kwargs={"pk": notification.pk})
        )

        assert listing.status_code == 200
        assert notification.pk in {
            item["id"] for item in listing.data.get("results", [])
        }
        assert detail.status_code == 200
        assert cleared.status_code == 204
        assert DeletedNotification.objects.filter(
            notification=notification, user=user
        ).exists()
        assert not DeletedNotification.objects.filter(
            notification=notification, user=another_user
        ).exists()
        assert notification.pk not in {
            item["id"]
            for item in self.client.get(reverse("activities-list")).data.get(
                "results", []
            )
        }
        # The second member can still see their group-only unread notification.
        self.client.force_authenticate(user=another_user)
        assert notification.pk in {
            item["id"]
            for item in self.client.get(reverse("notifications-list")).data.get(
                "results", []
            )
        }

    def test_group_only_bulk_clear_is_scoped_and_deduplicated(
        self,
        user: User,
        another_user: User,
        group,
        notification: Notification,
    ) -> None:
        """Bulk clear respects group visibility without affecting other users."""
        extra_group = type(group).objects.create(name="bulk_clear_extra_group")
        user.groups.add(group, extra_group)
        another_user.groups.add(group)
        notification.recipient.add(user)
        notification.group.add(group, extra_group)
        notification.mark_as_seen(user)
        group_only = Notification.objects.create_notification(
            verb="group only",
            actor=user,
            is_sent=True,
            groups=group,
        )
        group_only.mark_as_seen(user)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("activities-clear-activities"))

        assert response.status_code == 204
        assert DeletedNotification.objects.filter(user=user).count() == 2
        assert DeletedNotification.objects.filter(user=another_user).count() == 0
        assert self.client.get(reverse("activities-list")).data["count"] == 0

    def test_nonmember_staff_cannot_soft_delete_group_notification(
        self, admin_user: User, group, notification: Notification
    ) -> None:
        """Superuser status alone cannot clear a group-targeted notice."""
        notification.group.add(group)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(
            reverse("activities-clear-notification", kwargs={"pk": notification.pk})
        )

        assert response.status_code == 404
        assert not DeletedNotification.objects.filter(
            user=admin_user, notification=notification
        ).exists()

    @patch.object(config, "api_allow_list", False)
    def test_list_method_disabled(self, user: User) -> None:
        """
        Test that the list method is disabled when `api_allow_list` is False in the config.

        Args:
        ----
            user (User): A regular user instance.

        Asserts:
        -------
            - The response status code is 405 (Method Not Allowed).
        """
        self.client.force_authenticate(user=user)
        url = reverse("activities-list")
        response = self.client.get(url)
        assert response.status_code == 405  # Method Not Allowed

    @patch.object(config, "api_allow_retrieve", False)
    def test_retrieve_method_disabled(
        self, user: User, notification: Notification
    ) -> None:
        """
        Test that the retrieve method is disabled when `api_allow_retrieve` is False in the config.

        Args:
        ----
            user (User): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 405 (Method Not Allowed).
        """
        self.client.force_authenticate(user=user)
        url = reverse("activities-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 405  # Method Not Allowed

    @patch.object(config, "include_serializer_full_details", True)
    def test_full_details_serializer_used(
        self, user: User, notification: Notification
    ) -> None:
        """
        Test that the safe full details serializer is used when configured.

        Args:
        ----
            user (User): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The response data does not expose other users' recipient/read-state fields.
        """
        self.client.force_authenticate(user=user)
        notification.recipient.add(user)
        notification.seen_by.add(user)

        url = reverse("activities-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "recipient" not in response.data
        assert "seen_by" not in response.data
        assert "group" not in response.data
        assert "data" not in response.data

    def test_clear_activities(self, user: User, notification: Notification) -> None:
        """
        Test the clear_activities action to soft delete all notifications.

        Args:
        ----
            user (User): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 204 (No Content).
            - The number of soft-deleted notifications matches the number of sent notifications.
        """
        self.client.force_authenticate(user=user)
        notification.recipient.add(user)
        # First, mark all notifications as seen
        url = reverse("notifications-mark-all-as-seen")
        self.client.get(url)

        url = reverse("activities-clear-activities")
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert (
            Notification.objects.sent().count() == DeletedNotification.objects.count()
        )

    def test_clear_notification(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test the clear_notification action to soft delete a specific notification.

        Args:
        ----
            admin_user (User): An admin user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 204 (No Content).
            - The specific notification is found in DeletedNotification.
        """
        self.client.force_authenticate(user=admin_user)
        notification.recipient.add(admin_user)
        notification.seen_by.add(admin_user)

        url = reverse("activities-clear-notification", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert DeletedNotification.objects.filter(notification=notification).exists()

    def test_staff_clear_all_does_not_clear_another_users_notification(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        notification.recipient.add(user)
        notification.seen_by.add(user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("activities-clear-activities"))

        assert response.status_code == 204
        assert not DeletedNotification.objects.filter(
            notification=notification, user=admin_user
        ).exists()

    def test_staff_cannot_soft_delete_another_users_notification(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        notification.recipient.add(user)
        notification.seen_by.add(user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(
            reverse("activities-clear-notification", kwargs={"pk": notification.pk})
        )

        assert response.status_code == 404
        assert not DeletedNotification.objects.filter(
            notification=notification, user=admin_user
        ).exists()

    @patch.object(config, "include_hard_delete", True)
    def test_delete_activities(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test the delete_activities action to hard delete all notifications.

        Args:
        ----
            admin_user (User): An admin user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 204 (No Content).
            - No notifications remain in the database.
        """

        notification.recipient.add(admin_user)
        self.client.force_authenticate(user=admin_user)
        # First, mark all notifications as seen
        url = reverse("notifications-mark-all-as-seen")
        self.client.get(url)

        url = reverse("activities-delete-activities")
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert not Notification.objects.all_notifications()

    @patch.object(config, "include_hard_delete", True)
    def test_delete_notification(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test the delete_notification action to hard delete a specific notification.

        Args:
        ----
            admin_user (User): An admin user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 204 (No Content).
            - The specific notification does not exist in the database.
        """
        notification.recipient.add(admin_user)
        notification.seen_by.add(admin_user)
        self.client.force_authenticate(user=admin_user)
        url = reverse("activities-delete-notification", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert not Notification.objects.filter(pk=notification.pk).exists()
