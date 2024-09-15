import sys
from typing import List
from unittest.mock import Mock

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import Client
from django.contrib import admin
from django_notification.models import (
    Notification,
    NotificationRecipient,
    NotificationSeen,
)
from django_notification.admin.notification import (
    NotificationAdmin,
    NotificationRecipientInline,
    NotificationSeenInline,
)
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.admin,
    pytest.mark.admin_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotificationAdminSite:
    """
    Test suite for the NotificationAdmin and associated inlines in the Django admin interface.
    """

    def mock_request(self, user: User) -> Mock:
        """
        Create a mock request object with a user for testing.

        Args:
        ----
            user: The user to associate with the mock request.

        Returns:
        -------
            Mock: A mock request object with the user attribute set.
        """
        request = Mock()
        request.user = user
        return request

    def test_notification_admin_list_display(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test that the list display fields in the NotificationAdmin interface
        are rendered correctly in the Django admin changelist view.

        Asserts:
        -------
            - The changelist view returns a 200 status code.
            - The list display includes the fields 'id', 'get_title', 'is_sent', 'public', and 'timestamp'.
        """
        client = Client()
        client.login(username="admin", password="password")

        url = reverse("admin:django_notification_notification_changelist")
        response = client.get(url)

        assert (
            response.status_code == 200
        ), "Expected changelist view to return status 200."
        content = response.content.decode()
        assert "id" in content, "'id' field is missing in the list display."
        assert (
            "get_title" in content
        ), "'get_title' field is missing in the list display."
        assert "is_sent" in content, "'is_sent' field is missing in the list display."
        assert "public" in content, "'public' field is missing in the list display."
        assert (
            "timestamp" in content
        ), "'timestamp' field is missing in the list display."

    def test_notification_admin_inlines(
        self,
        admin_user: User,
        notification: Notification,
        notification_recipient: NotificationRecipient,
        notification_seen: NotificationSeen,
    ) -> None:
        """
        Test that NotificationRecipientInline and NotificationSeenInline are correctly displayed
        in the NotificationAdmin change form view.

        Asserts:
        -------
            - The change form view returns a 200 status code.
            - The change form view includes the "Notification Recipients" and "Notification Seen" sections.
        """
        client = Client()
        client.login(username="admin", password="password")

        url = reverse(
            "admin:django_notification_notification_change", args=[notification.id]
        )
        response = client.get(url)

        assert (
            response.status_code == 200
        ), "Expected change form view to return status 200."
        content = response.content.decode()
        assert (
            "Notification Recipients" in content
        ), "'Notification Recipients' section is missing in the change form view."
        assert (
            "Notification Seen" in content
        ), "'Notification Seen' section is missing in the change form view."

    def test_notification_admin_queryset(
        self, admin_user: User, notification: Notification
    ) -> None:
        """
        Test that NotificationAdmin's queryset method selects related fields using `select_related`
        to optimize query performance.

        Asserts:
        -------
            - The queryset includes the use of `select_related` for 'actor_content_type', 'target_content_type', and 'action_object_content_type' fields.
        """
        admin_site = admin.site
        model_admin = NotificationAdmin(Notification, admin_site)
        request = self.mock_request(admin_user)

        queryset = model_admin.get_queryset(request)

        # Check that the query uses select_related for specified fields
        assert "actor_content_type" in str(
            queryset.query
        ), "'actor_content_type' field not optimized with select_related."
        assert "target_content_type" in str(
            queryset.query
        ), "'target_content_type' field not optimized with select_related."
        assert "action_object_content_type" in str(
            queryset.query
        ), "'action_object_content_type' field not optimized with select_related."

    def test_notification_recipient_inline_queryset(
        self,
        admin_user: User,
        notification: Notification,
        notification_recipient: NotificationRecipient,
    ) -> None:
        """
        Test that NotificationRecipientInline's queryset method selects related fields using `select_related`.

        Asserts:
        -------
            - The queryset includes the use of `select_related` for 'notification' and 'recipient' fields.
        """
        admin_site = admin.site
        inline = NotificationRecipientInline(NotificationRecipient, admin_site)
        request = self.mock_request(admin_user)

        queryset = inline.get_queryset(request)

        # Check that the query uses select_related for specified fields
        assert "notification" in str(
            queryset.query
        ), "'notification' field not optimized with select_related."
        assert "recipient" in str(
            queryset.query
        ), "'recipient' field not optimized with select_related."

    def test_notification_seen_inline_queryset(
        self,
        admin_user: User,
        notification: Notification,
        notification_seen: NotificationSeen,
    ) -> None:
        """
        Test that NotificationSeenInline's queryset method selects related fields using `select_related`.

        Asserts:
        -------
            - The queryset includes the use of `select_related` for 'notification' and 'user' fields.
        """
        admin_site = admin.site
        inline = NotificationSeenInline(NotificationSeen, admin_site)
        request = self.mock_request(admin_user)

        queryset = inline.get_queryset(request)

        # Check that the query uses select_related for specified fields
        assert "notification" in str(
            queryset.query
        ), "'notification' field not optimized with select_related."
        assert "user" in str(
            queryset.query
        ), "'user' field not optimized with select_related."

    def test_mark_all_as_sent_action(
        self, admin_user: User, notifications: List[Notification]
    ) -> None:
        """
        Test the 'mark_as_sent' action in the NotificationAdmin interface for bulk marking notifications as sent.

        Asserts:
        -------
            - The action triggers a redirect (302 status code).
            - All selected notifications are marked as sent.
        """
        client = Client()
        client.login(username="admin", password="password")

        url = reverse("admin:django_notification_notification_changelist")
        post_data = {
            "action": "mark_as_sent",
            "_selected_action": [
                str(n.id) for n in notifications
            ],  # Select all notifications
        }

        response = client.post(url, post_data)

        # Check if the action was successful and redirected back
        assert (
            response.status_code == 302
        ), "Expected redirect status code after action."

        # Reload notifications from the database and verify that they are marked as sent
        for notification in notifications:
            notification.refresh_from_db()
            assert (
                notification.is_sent is True
            ), f"Notification {notification.id} was not marked as sent."
