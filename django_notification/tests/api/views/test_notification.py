import sys
from typing import Type
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.permissions import IsAuthenticated
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

    def test_get_queryset_for_staff(
        self, admin_user: Type[User], notification: Notification
    ) -> None:
        """
        Test that staff users retrieve all unseen notifications.

        Args:
        ----
            admin_user (Type[User]): An admin user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The number of unseen notifications matches the expected count.
        """
        # Set config to test extra permission attribute
        config.api_extra_permission_class = IsAuthenticated

        self.client.force_authenticate(user=admin_user)
        url = reverse("notifications-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert (
            len(response.data.get("results", []))
            == Notification.queryset.unseen(unseen_by=admin_user).count()
        )

    def test_get_queryset_for_non_staff(
        self, user: Type[User], notification: Notification
    ) -> None:
        """
        Test that non-staff users retrieve unseen notifications based on their group memberships.

        Args:
        ----
            user (Type[User]): A regular user instance.
            notification (Notification): A notification instance.

        Asserts:
        -------
            - The response status code is 200.
            - The number of unseen notifications matches the expected count.
        """
        self.client.force_authenticate(user=user)
        url = reverse("notifications-list")
        response = self.client.get(url)
        assert response.status_code == 200
        assert (
            len(response.data.get("results", []))
            == Notification.queryset.unseen(unseen_by=user).count()
        )

    def test_retrieve_notification(
        self, user: Type[User], notification: Notification
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
        assert Notification.queryset.seen(seen_by=user).exists()

    def test_mark_all_as_seen(
        self, user: Type[User], notification: Notification
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
        self.client.force_authenticate(user=user)
        url = reverse("notifications-mark-all-as-seen")
        response = self.client.get(url)
        assert response.status_code == 200
        assert "Notifications marked as seen" in response.data.get("detail", "")

    @patch.object(config, "api_allow_list", False)
    def test_list_method_disabled(self, user: Type[User]) -> None:
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
        self, user: Type[User], notification: Notification
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
        self, user: Type[User], notification: Notification
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
