import sys
import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from django_notification.api.paginations.limit_offset_pagination import (
    DefaultLimitOffSetPagination,
)
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.api,
    pytest.mark.api_paginations,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestDefaultLimitOffsetPagination:
    """
    Test suite for the DefaultLimitOffSetPagination class.
    """

    def setup_method(self) -> None:
        """
        Initialize APIRequestFactory for each test.
        """
        self.factory = APIRequestFactory()

    def test_get_limit_with_valid_limit(self) -> None:
        """
        Test that a valid limit provided in query parameters is returned correctly.

        Asserts:
        -------
            - The limit specified in the query parameters is correctly processed and returned.
        """
        request = self.factory.get("/some-url", {"limit": "5"})
        drf_request = Request(request)  # Wrap in DRF request
        paginator = DefaultLimitOffSetPagination()
        limit = paginator.get_limit(drf_request)
        assert (
            limit == 5
        ), "The limit was not correctly returned for a valid limit parameter."

    def test_get_limit_with_default_limit(self) -> None:
        """
        Test that the default limit is returned when no limit is provided in query parameters.

        Asserts:
        -------
            - The default limit of the paginator is returned when no limit is specified in the request.
        """
        request = self.factory.get("/some-url")
        drf_request = Request(request)  # Wrap in DRF request
        paginator = DefaultLimitOffSetPagination()
        limit = paginator.get_limit(drf_request)
        assert (
            limit == paginator.default_limit
        ), "The default limit was not correctly returned when no limit was provided."

    def test_get_limit_with_invalid_limit(self) -> None:
        """
        Test that the default limit is returned when an invalid limit is provided.

        Asserts:
        -------
            - The default limit is returned when the limit parameter is invalid (e.g., non-integer value).
        """
        request = self.factory.get("/some-url", {"limit": "abc"})
        drf_request = Request(request)  # Wrap in DRF request
        paginator = DefaultLimitOffSetPagination()
        limit = paginator.get_limit(drf_request)
        assert (
            limit == paginator.default_limit
        ), "The default limit was not correctly returned for an invalid limit parameter."

    def test_get_limit_with_limit_above_max_limit(self) -> None:
        """
        Test that the max limit is returned when the limit exceeds the maximum allowed value.

        Asserts:
        -------
            - The max limit is returned when the limit parameter exceeds the defined maximum limit.
        """
        request = self.factory.get("/some-url", {"limit": "150"})
        drf_request = Request(request)  # Wrap in DRF request
        paginator = DefaultLimitOffSetPagination()
        limit = paginator.get_limit(drf_request)
        assert (
            limit == paginator.max_limit
        ), "The max limit was not correctly enforced for a limit exceeding the maximum allowed value."

    def test_get_limit_with_limit_below_min_limit(self) -> None:
        """
        Test that the default limit is returned when the provided limit is below the minimum allowed value.

        Asserts:
        -------
            - The default limit is returned when the limit parameter is below the minimum allowed limit.
        """
        request = self.factory.get("/some-url", {"limit": "0"})
        drf_request = Request(request)  # Wrap in DRF request
        paginator = DefaultLimitOffSetPagination()
        limit = paginator.get_limit(drf_request)
        assert (
            limit == paginator.default_limit
        ), "The default limit was not correctly enforced for a limit below the minimum allowed value."
