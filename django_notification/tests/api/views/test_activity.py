import sys

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from django_notification.models import DeletedNotification
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

    def test_get_queryset_for_staff(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test that staff users can retrieve all seen notifications.

        Args:
        ----
            admin_user (User): An admin user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The number of notifications returned matches the number of seen notifications for the admin user.
        """
        self.client.force_authenticate(user=admin_user)
        url = reverse("activities-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert (
            len(response.data.get("results"))
            == Notification.objects.seen(seen_by=admin_user).count()
        )

    def test_get_queryset_for_non_staff(
        self, user: User, notification: Notification
    ) -> None:
        """
        Test that non-staff users retrieve notifications based on their group memberships.

        Args:
        ----
            user (User): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The number of notifications returned matches the number of seen notifications for the user.
        """
        self.client.force_authenticate(user=user)
        url = reverse("activities-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert (
            len(response.data.get("results"))
            == Notification.objects.seen(seen_by=user, recipients=user).count()
        )

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
        Test that the full details serializer is used when `include_serializer_full_details` is True.

        Args:
        ----
            user (User): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The response data includes 'recipient' and 'seen_by' fields.
        """
        self.client.force_authenticate(user=user)
        notification.recipient.add(user)
        notification.seen_by.add(user)

        url = reverse("activities-detail", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert "recipient", "seen_by" in response.data

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
        notification.seen_by.add(admin_user)

        url = reverse("activities-clear-notification", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert DeletedNotification.objects.filter(notification=notification).exists()

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
        notification.seen_by.add(admin_user)
        self.client.force_authenticate(user=admin_user)
        url = reverse("activities-delete-notification", kwargs={"pk": notification.pk})
        response = self.client.get(url)
        assert response.status_code == 204  # No Content
        assert not Notification.objects.filter(pk=notification.pk).exists()
