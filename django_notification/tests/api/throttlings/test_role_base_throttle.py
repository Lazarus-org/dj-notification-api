import sys

import pytest
from django.contrib.auth.models import User
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.cache import cache

from django_notification.api.throttlings.role_base_throttle import (
    RoleBasedUserRateThrottle,
)
from django_notification.settings.conf import config
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_throttlings,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


class MockView(APIView):
    """
    A mock API view to test the RoleBasedUserRateThrottle class.

    This view applies the RoleBasedUserRateThrottle to simulate throttle behavior
    for testing purposes.
    """

    throttle_classes = [RoleBasedUserRateThrottle]

    def get(self, request: Request) -> Response:
        """
        Handle GET requests for this view.

        Args:
        ----
            request (Request): The HTTP request object.

        Returns:
        -------
            Response: The HTTP response with a success message.
        """
        return Response({"message": "Request allowed"})


@pytest.mark.django_db
class TestRoleBasedUserRateThrottle:
    """
    Test suite for the RoleBasedUserRateThrottle class.

    This class contains tests to verify the throttling behavior for regular
    and staff users based on the configured rate limits.
    """

    def setup_method(self) -> None:
        """
        Setup method for initializing test client, request factory, and mock view.
        """
        self.factory = APIRequestFactory()
        self.view = MockView.as_view()
        self.client = APIClient()

    def teardown_method(self) -> None:
        """
        Teardown method to clear the cache and reset throttle settings.
        """
        cache.clear()
        config.staff_user_throttle_rate = "100/minute"
        config.authenticated_user_throttle_rate = "30/minute"

    def test_regular_user_throttle(self, user: User) -> None:
        """
        Test throttling behavior for regular authenticated users.

        This test verifies that regular users are correctly throttled according
        to the 'authenticated_user_throttle_rate' configuration setting.

        Args:
        ----
            user (User): A regular user instance.

        Asserts:
        -------
            - The user can make up to 3 requests within the throttle limit.
            - The 4th request is throttled and returns a 429 status code.
        """
        config.authenticated_user_throttle_rate = "3/min"
        request = self.factory.get("/mock-view/")
        force_authenticate(request, user=user)

        for _ in range(3):
            response = self.view(request)
            assert response.status_code == 200

        # 4th request should be throttled
        response = self.view(request)
        assert response.status_code == 429
        assert "Request was throttled." in response.data["detail"]

    def test_staff_user_throttle(self, admin_user: User) -> None:
        """
        Test throttling behavior for staff users.

        This test verifies that staff users are correctly throttled according
        to the 'staff_user_throttle_rate' configuration setting.

        Args:
        ----
            admin_user (User): A staff user instance.

        Asserts:
        -------
            - The staff user can make up to 5 requests within the throttle limit.
            - The 6th request is throttled and returns a 429 status code.
        """
        config.staff_user_throttle_rate = "5/min"
        request = self.factory.get("/mock-view/")
        force_authenticate(request, user=admin_user)

        for _ in range(5):
            response = self.view(request)
            assert response.status_code == 200

        # 6th request should be throttled
        response = self.view(request)
        assert response.status_code == 429
        assert "Request was throttled." in response.data["detail"]
