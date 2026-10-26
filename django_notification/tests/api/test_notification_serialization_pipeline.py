"""Regression tests for model-backed notification API serialization."""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.api.views.activity import ActivityViewSet
from django_notification.api.views.notification import NotificationViewSet
from django_notification.models import Notification
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


@patch.object(config, "exclude_serializer_null_fields", False)
@patch.object(config, "notification_serializer_fields", None)
def test_default_serializer_matches_legacy_dictionary(
    notification: Notification, notification_dict: dict
) -> None:
    """Model-backed feeds retain the historical compact JSON representation."""
    model_data = NotificationDynamicSerializer(notification).data
    legacy_data = NotificationDynamicSerializer(notification_dict).data

    assert model_data == legacy_data
    assert set(model_data) == {
        "title",
        "id",
        "description",
        "status",
        "link",
        "timestamp",
    }


@patch.object(config, "exclude_serializer_null_fields", True)
def test_model_serializer_honors_null_field_option(notification: Notification) -> None:
    """Null-field suppression works without a ``values()`` projection."""
    assert notification.link is None
    serialized = NotificationDynamicSerializer(notification).data
    assert "link" not in serialized


@patch.object(config, "notification_serializer_fields", None)
@patch.object(config, "notification_serializer_class", None)
@patch.object(config, "include_serializer_full_details", False)
@patch.object(config, "exclude_serializer_null_fields", False)
def test_unseen_list_uses_models_and_keeps_compact_contract(
    notification: Notification, user: User, group: Group
) -> None:
    """A group recipient sees the original compact fields, once per record."""
    notification.recipient.add(user)
    user.groups.add(group)
    notification.group.add(group)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("notifications-list"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"] == [
        NotificationDynamicSerializer(notification).data
    ]


@patch.object(config, "notification_serializer_fields", None)
@patch.object(config, "notification_serializer_class", None)
@patch.object(config, "include_serializer_full_details", False)
def test_seen_list_uses_models_and_keeps_compact_contract(
    notification: Notification, user: User, group: Group
) -> None:
    """Group activity remains readable and serialized for the acting user."""
    user.groups.add(group)
    notification.group.add(group)
    notification.seen_by.add(user)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("activities-list"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == notification.pk
    assert response.data["results"][0]["title"] == str(notification)


@patch.object(config, "include_serializer_full_details", True)
def test_configured_full_list_returns_model_details(
    notification: Notification, user: User
) -> None:
    """Full-detail settings do not depend on query-level dictionary projection."""
    notification.recipient.add(user)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("notifications-list"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == notification.pk
    assert "recipient" not in response.data["results"][0]
    assert "seen_by" not in response.data["results"][0]
    assert "data" not in response.data["results"][0]


def test_get_queryset_returns_models_even_with_compat_argument(
    notification: Notification, user: User
) -> None:
    """The old ``display_detail`` view argument no longer changes row type."""
    notification.recipient.add(user)
    view = NotificationViewSet()
    view.request = type("RequestStub", (), {"user": user, "query_params": {}})()

    assert view.get_queryset().get().pk == notification.pk
    assert isinstance(view.get_queryset(display_detail=True).get(), Notification)

    notification.seen_by.add(user)
    activities = ActivityViewSet()
    activities.request = view.request
    assert isinstance(activities.get_queryset().get(), Notification)
    assert isinstance(activities.get_queryset(display_detail=True).get(), Notification)


def test_legacy_manager_projection_types_remain_unchanged(
    notification: Notification, user: User
) -> None:
    """Published legacy manager methods remain compatible during migration."""
    notification.recipient.add(user)
    compact = Notification.objects.sent(recipients=user).get()
    detail = Notification.objects.sent(recipients=user, display_detail=True).get()

    assert isinstance(compact, dict)
    assert compact["id"] == notification.pk
    assert isinstance(detail, Notification)


def test_custom_list_serializer_receives_notification_models(
    notification: Notification, user: User
) -> None:
    """Configured serializer overrides still receive a real model instance."""
    from rest_framework.serializers import ModelSerializer

    class CompactCustomSerializer(ModelSerializer):
        """Sample custom integration serializer."""

        class Meta:
            model = Notification
            fields = ("id", "description")

    notification.recipient.add(user)
    client = APIClient()
    client.force_authenticate(user=user)

    with patch.object(config, "include_serializer_full_details", False):
        with patch.object(
            config, "notification_serializer_class", CompactCustomSerializer
        ):
            response = client.get(reverse("notifications-list"))

    assert response.status_code == 200
    assert response.data["results"] == [
        {"id": notification.pk, "description": notification.description}
    ]
