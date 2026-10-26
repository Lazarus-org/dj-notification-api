import sys
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.models.notification import Notification
from django_notification.settings.conf import config
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_views,
    pytest.mark.api_views_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationViewSet:
    """
    Test suite for the NotificationViewSet class.

    This class contains tests for various actions and methods provided by the
    NotificationViewSet. It includes tests for retrieving notifications, marking
    notifications as seen, and configuration-based method enabling/disabling.
    """

    def setup_method(self) -> None:
        """
        Initialize the test client before each test.
        """
        self.client = APIClient()

    @patch.object(config, "exclude_serializer_null_fields", False)
    def test_staff_list_is_scoped_to_direct_recipients(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        """Staff status must not expose a notification addressed to another user."""
        notification.recipient.add(user)

        self.client.force_authenticate(user=admin_user)
        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        assert notification.pk not in {
            item["id"] for item in response.data.get("results", [])
        }

    @patch.object(config, "include_serializer_full_details", False)
    @patch.object(config, "notification_serializer_class", None)
    def test_staff_can_list_own_direct_notifications(
        self, admin_user: User, notification: Notification
    ) -> None:
        """Staff users can still see notifications explicitly addressed to them."""
        notification.recipient.add(admin_user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }
        result = next(
            item
            for item in response.data.get("results", [])
            if item["id"] == notification.pk
        )
        assert "recipient" not in result
        assert "seen_by" not in result

    def test_staff_cannot_retrieve_another_users_notification(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        notification.recipient.add(user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(
            reverse("notifications-detail", kwargs={"pk": notification.pk})
        )

        assert response.status_code == 404

    def test_list_contains_direct_notifications(
        self, user: User, notification: Notification
    ) -> None:
        """A regular user receives notifications directly addressed to them."""
        notification.recipient.add(user)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_group_only_notification_is_visible_to_group_members(
        self, user: User, group: Group
    ) -> None:
        """An explicitly targeted group is a valid notification recipient."""
        user.groups.add(group)
        notification = Notification.objects.create_notification(
            verb="group notice",
            actor=user,
            description="A group-only notification",
            is_sent=True,
        )
        notification.group.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_group_member_can_retrieve_and_mark_seen(
        self, user: User, group: Group, notification: Notification
    ) -> None:
        """Group-only notifications support per-user detail and read state."""
        user.groups.add(group)
        notification.group.add(group)
        self.client.force_authenticate(user=user)

        response = self.client.get(
            reverse("notifications-detail", kwargs={"pk": notification.pk})
        )

        assert response.status_code == 200
        assert notification.seen.filter(user=user).exists()

    def test_nonmember_cannot_read_group_notification(
        self,
        admin_user: User,
        user: User,
        group: Group,
        notification: Notification,
    ) -> None:
        """A superuser outside the group has no implicit notification access."""
        user.groups.add(group)
        notification.group.add(group)
        self.client.force_authenticate(user=admin_user)

        listing = self.client.get(reverse("notifications-list"))
        detail = self.client.get(
            reverse("notifications-detail", kwargs={"pk": notification.pk})
        )

        assert listing.status_code == 200
        assert notification.pk not in {
            item["id"] for item in listing.data.get("results", [])
        }
        assert detail.status_code == 404
        assert not notification.seen.filter(user=admin_user).exists()

    def test_staff_member_sees_group_notification(
        self, admin_user: User, group: Group, notification: Notification
    ) -> None:
        """Staff can read notifications from groups they actually belong to."""
        admin_user.groups.add(group)
        notification.group.add(group)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        assert notification.pk in {
            item["id"] for item in response.data.get("results", [])
        }

    def test_direct_and_multiple_group_targets_produce_one_item(
        self, user: User, group: Group, notification: Notification
    ) -> None:
        """Overlapping recipient/group paths must not duplicate feed rows."""
        another_group = Group.objects.create(name="another_target_group")
        user.groups.add(group, another_group)
        notification.recipient.add(user)
        notification.group.add(group, another_group)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("notifications-list"))

        assert response.status_code == 200
        ids = [item["id"] for item in response.data.get("results", [])]
        assert ids.count(notification.pk) == 1

    def test_group_membership_revocation_removes_access(
        self, user: User, group: Group, notification: Notification
    ) -> None:
        """Current membership, not historical membership, controls access."""
        user.groups.add(group)
        notification.group.add(group)
        self.client.force_authenticate(user=user)
        assert self.client.get(reverse("notifications-list")).data["count"] == 1

        user.groups.remove(group)

        assert (
            self.client.get(
                reverse("notifications-detail", kwargs={"pk": notification.pk})
            ).status_code
            == 404
        )
        assert self.client.get(reverse("notifications-list")).data["count"] == 0

    def test_mark_all_as_seen_handles_group_and_direct_targets_once(
        self, user: User, group: Group, notification: Notification
    ) -> None:
        """Bulk reads include group notifications and deduplicate overlapping targets."""
        other_group = Group.objects.create(name="another_markall_group")
        user.groups.add(group, other_group)
        notification.recipient.add(user)
        notification.group.add(group, other_group)
        group_only = Notification.objects.create_notification(
            verb="group only",
            actor=user,
            is_sent=True,
            groups=group,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("notifications-mark-all-as-seen"))

        assert response.status_code == 200
        assert "2 Notifications marked as seen." == response.data["detail"]
        assert notification.seen.filter(user=user).count() == 1
        assert group_only.seen.filter(user=user).count() == 1
        repeat = self.client.get(reverse("notifications-mark-all-as-seen"))
        assert repeat.data["detail"] == "0 Notifications marked as seen."

    def test_retrieve_notification(
        self, user: type[User], notification: Notification
    ) -> None:
        """
        Test the retrieve functionality to get a specific notification and mark it as seen.

        Args:
        ----
            user (Type[User]): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The notification is marked as seen by the user.
        """
        notification.recipient.add(user)
        self.client.force_authenticate(user=user)
        url = reverse("notifications-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert Notification.objects.seen(seen_by=user, recipients=user).exists()

    def test_mark_all_as_seen(
        self, user: type[User], notification: Notification
    ) -> None:
        """
        Test the mark_all_as_seen action to mark all notifications as seen for the user.

        Args:
        ----
            user (Type[User]): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The response data includes the detail message indicating notifications were marked as seen.
        """
        notification.recipient.add(user)
        self.client.force_authenticate(user=user)
        url = reverse("notifications-mark-all-as-seen")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Notifications marked as seen" in response.data.get("detail", "")
        assert (
            Notification.objects.seen(seen_by=user, recipients=user)
            .filter(pk=notification.pk)
            .exists()
        )

    def test_staff_mark_all_does_not_mark_another_users_notification(
        self, admin_user: User, user: User, notification: Notification
    ) -> None:
        notification.recipient.add(user)
        self.client.force_authenticate(user=admin_user)

        response = self.client.get(reverse("notifications-mark-all-as-seen"))

        assert response.status_code == 200
        assert (
            not Notification.objects.seen(seen_by=admin_user, recipients=admin_user)
            .filter(pk=notification.pk)
            .exists()
        )

    @patch.object(config, "api_allow_list", False)
    def test_list_method_disabled(self, user: type[User]) -> None:
        """
        Test that the list method is disabled when `api_allow_list` is False in the config.

        Args:
        ----
            user (Type[User]): A regular user instance.

        Asserts:
        -------
            - The response status code is 405 (Method Not Allowed).
        """
        self.client.force_authenticate(user=user)
        url = reverse("notifications-list")
        response = self.client.get(url)
        assert response.status_code == 405  # Method Not Allowed

    @patch.object(config, "api_allow_retrieve", False)
    def test_retrieve_method_disabled(
        self, user: type[User], notification: Notification
    ) -> None:
        """
        Test that the retrieve method is disabled when `api_allow_retrieve` is False in the config.

        Args:
        ----
            user (Type[User]): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 405 (Method Not Allowed).
        """
        notification.recipient.add(user)
        self.client.force_authenticate(user=user)
        url = reverse("notifications-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 405  # Method Not Allowed

    @patch.object(config, "include_serializer_full_details", True)
    def test_full_details_serializer_used(
        self, user: type[User], notification: Notification
    ) -> None:
        """
        Test that the full details serializer is used when `include_serializer_full_details` is True in the config.

        Args:
        ----
            user (Type[User]): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
        """
        notification.recipient.add(user)
        self.client.force_authenticate(user=user)
        url = reverse("notifications-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "recipient" not in response.data
        assert "seen_by" not in response.data
        assert "group" not in response.data
        assert "data" not in response.data
