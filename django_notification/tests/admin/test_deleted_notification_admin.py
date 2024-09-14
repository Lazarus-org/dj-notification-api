import sys
from unittest.mock import Mock
import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django_notification.models import DeletedNotification
from django_notification.admin import DeletedNotificationAdmin
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.admin,
    pytest.mark.admin_deleted_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestDeletedNotificationAdmin:
    """
    Test suite for the DeletedNotificationAdmin class in the Django admin interface.
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

    def test_deleted_notification_admin_list_display(
        self, admin_user: User, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test that the list display fields in the DeletedNotificationAdmin interface
        are rendered correctly in the Django admin changelist view.

        Asserts:
        -------
            - The changelist view returns a 200 status code.
            - The list display includes the fields 'notification_id', 'get_title', 'get_deleted_by', and 'deleted_at'.
        """
        client = Client()
        client.login(username="admin", password="password")

        url = reverse("admin:django_notification_deletednotification_changelist")
        response = client.get(url)

        assert (
            response.status_code == 200
        ), "Expected changelist view to return status 200."
        content = response.content.decode()
        assert (
            "notification_id" in content
        ), "'notification_id' field is missing in the list display."
        assert (
            "get_title" in content
        ), "'get_title' field is missing in the list display."
        assert (
            "get_deleted_by" in content
        ), "'get_deleted_by' field is missing in the list display."
        assert (
            "deleted_at" in content
        ), "'deleted_at' field is missing in the list display."

    def test_deleted_notification_admin_filters(
        self, admin_user: User, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test that the filters in the DeletedNotificationAdmin interface work correctly.

        Asserts:
        -------
            - The filtered changelist view returns a 200 status code.
            - The changelist view includes the "Deleted Notifications" section.
        """
        client = Client()
        client.login(username="admin", password="password")

        url = reverse("admin:django_notification_deletednotification_changelist")
        response = client.get(
            url + "?deleted_at__gte=2024-01-01+00%3A00%3A00%2B00%3A00"
        )

        assert (
            response.status_code == 200
        ), "Expected filtered changelist view to return status 200."
        assert (
            "Deleted Notifications" in response.content.decode()
        ), "'Deleted Notifications' filter not applied."

    def test_deleted_notification_admin_search(
        self, admin_user: User, user: User, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test the search functionality in DeletedNotificationAdmin for searching by notification ID
        and username of the user who deleted the notification.

        Asserts:
        -------
            - The search by notification ID returns the correct result.
            - The search by the username of the user who deleted the notification returns the correct result.
        """
        admin_site = admin.site
        model_admin = DeletedNotificationAdmin(DeletedNotification, admin_site)
        request = self.mock_request(admin_user)

        # Test search by notification ID
        queryset, _ = model_admin.get_search_results(
            request,
            DeletedNotification.objects.all(),
            deleted_notification.notification.id,
        )
        assert (
            queryset.count() == 1
        ), "Search by notification ID did not return the expected result."

        # Test search by the username of the user who deleted this notification
        queryset, _ = model_admin.get_search_results(
            request, DeletedNotification.objects.all(), user.username
        )
        assert (
            queryset.count() == 1
        ), "Search by username did not return the expected result."

    def test_deleted_notification_admin_queryset(
        self, admin_user: User, deleted_notification: DeletedNotification
    ) -> None:
        """
        Test that the queryset in DeletedNotificationAdmin selects related fields using `select_related`
        to optimize query performance.

        Asserts:
        -------
            - The queryset includes the use of `select_related` for the 'notification' and 'user' fields.
        """
        admin_site = admin.site
        model_admin = DeletedNotificationAdmin(DeletedNotification, admin_site)
        request = self.mock_request(admin_user)

        queryset = model_admin.get_queryset(request)

        # Check that the query uses select_related for 'notification' and 'user' fields
        assert "notification" in str(
            queryset.query
        ), "'notification' field not optimized with select_related."
        assert "user" in str(
            queryset.query
        ), "'user' field not optimized with select_related."
