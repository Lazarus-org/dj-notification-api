"""Security regressions for personal notification API and state mutations."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.api.serializers.notification import NotificationSerializer
from django_notification.api.serializers.self_service_notification import (
    NotificationSelfServiceSerializer,
)
from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationSeen,
)
from django_notification.models.permissions.notification_permission import (
    NotificationPermission,
)
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_model_permission_and_queryset_agree_for_direct_and_group_recipients(
    notification: Notification, user: User, another_user: User, group: Group
) -> None:
    """The same visibility contract applies at both model and query levels."""
    permission = NotificationPermission(notification)
    notification.group.add(group)
    user.groups.add(group)
    notification.recipient.add(another_user)

    for recipient in (user, another_user):
        assert (
            Notification.objects.visible_to(recipient)
            .filter(pk=notification.pk)
            .exists()
        )
        assert permission.user_has_permission(recipient)

    user.groups.remove(group)
    assert not permission.user_has_permission(user)
    user.groups.add(group)
    user.is_active = False
    assert not permission.user_has_permission(user)
    assert not Notification.objects.visible_to(user).exists()


def test_direct_recipient_without_groups_attribute_uses_same_policy(
    notification: Notification, user: User
) -> None:
    """A custom user lacking the groups relation can still receive directly."""
    notification.recipient.add(user)
    principal = SimpleNamespace(pk=user.pk, is_authenticated=True, is_active=True)
    permission = NotificationPermission(notification)
    assert (
        Notification.objects.visible_to(principal).filter(pk=notification.pk).exists()
    )
    assert permission.user_has_permission(principal)
    assert not permission.user_has_permission(
        SimpleNamespace(pk=None, is_authenticated=False, is_active=False)
    )


@patch.object(config, "include_serializer_full_details", True)
def test_full_personal_list_does_not_expose_other_recipients(
    notification: Notification, user: User, another_user: User, group: Group
) -> None:
    """Configured full-detail mode never grants visibility to private user data."""
    user.groups.add(group)
    notification.group.add(group)
    notification.recipient.add(another_user)
    notification.data = {"internal_token": "private"}
    notification.save(update_fields=["data"])
    notification.seen_by.add(another_user)
    response = _client(user).get(reverse("notifications-list"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["id"] == notification.pk
    assert item["verb"] == notification.verb
    for private_field in ("recipient", "group", "seen_by", "data"):
        assert private_field not in item
    assert "private" not in str(item)


def test_retrieval_uses_safe_serializer_even_when_full_admin_exists(
    notification: Notification, user: User, another_user: User, group: Group
) -> None:
    """Administrative serialization remains available, not via personal GET."""
    user.groups.add(group)
    notification.group.add(group)
    notification.recipient.add(another_user)
    notification.seen_by.add(another_user)
    notification.data = {"secret": "sensitive"}
    notification.save(update_fields=["data"])
    admin_data = NotificationSerializer(notification).data
    assert "recipient" in admin_data
    assert "seen_by" in admin_data

    response = _client(user).get(
        reverse("notifications-detail", kwargs={"pk": notification.pk})
    )
    assert response.status_code == 200
    assert response.data == NotificationSelfServiceSerializer(notification).data
    for private_field in ("recipient", "group", "seen_by", "data"):
        assert private_field not in response.data
    assert NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()


def test_activity_clear_requires_own_seen_state(
    notification: Notification, user: User, another_user: User, group: Group
) -> None:
    """The activity endpoint must not clear unread or foreign activities."""
    user.groups.add(group)
    another_user.groups.add(group)
    notification.group.add(group)
    notification.mark_as_seen(another_user)
    url = reverse("activities-clear-notification", kwargs={"pk": notification.pk})

    assert _client(user).get(url).status_code == 404
    assert not DeletedNotification.objects.filter(
        notification=notification, user=user
    ).exists()

    notification.mark_as_seen(user)
    assert _client(user).get(url).status_code == 204
    assert DeletedNotification.objects.filter(
        notification=notification, user=user
    ).exists()
    assert not DeletedNotification.objects.filter(
        notification=notification, user=another_user
    ).exists()
    assert _client(user).get(url).status_code == 404


@patch.object(config, "include_hard_delete", True)
def test_admin_detail_hard_delete_requires_own_seen_activity(
    notification: Notification, admin_user: User, user: User, group: Group
) -> None:
    """Staff status must not let a personal activity route delete foreign IDs."""
    notification.group.add(group)
    user.groups.add(group)
    notification.mark_as_seen(user)
    url = reverse("activities-delete-notification", kwargs={"pk": notification.pk})
    assert _client(admin_user).get(url).status_code == 404
    assert Notification.objects.filter(pk=notification.pk).exists()

    # Even direct but unread notifications are outside the activity feed.
    notification.recipient.add(admin_user)
    assert _client(admin_user).get(url).status_code == 404
    assert Notification.objects.filter(pk=notification.pk).exists()

    notification.mark_as_seen(admin_user)
    assert _client(admin_user).get(url).status_code == 204
    assert not Notification.objects.filter(pk=notification.pk).exists()


def test_group_membership_revocation_blocks_model_mutation(
    notification: Notification, user: User, group: Group
) -> None:
    """Dynamic group membership applies equally to model-level writes."""
    user.groups.add(group)
    notification.group.add(group)
    notification.mark_as_seen(user)
    user.groups.remove(group)

    assert not Notification.objects.visible_to(user).exists()
    with pytest.raises(PermissionError, match="permission"):
        notification.mark_as_seen(user)
