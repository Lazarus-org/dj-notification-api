"""Prevent action-specific permissions from being erased during view setup."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.permissions import BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.test import APIClient

from django_notification.api.views.activity import ActivityViewSet
from django_notification.models import Notification
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


class DenyAll(BasePermission):
    """Demonstrate that configured extra permissions are not bypassed."""

    def has_permission(self, request, view):
        """Reject every request."""
        return False


def _client(user):
    """Authenticate a test request as the supplied user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_action_permissions_survive_configurable_view_initialization():
    """DRF initkwargs cannot replace an admin guard with IsAuthenticated."""
    view = ActivityViewSet(permission_classes=[IsAdminUser])
    assert IsAuthenticated in view.permission_classes
    assert IsAdminUser in view.permission_classes


def test_subclass_permission_override_is_preserved():
    """Class-level custom permission declarations cannot be discarded either."""

    class StaffOnlyActivityViewSet(ActivityViewSet):
        permission_classes = [IsAdminUser]

    view = StaffOnlyActivityViewSet()
    assert IsAuthenticated in view.permission_classes
    assert IsAdminUser in view.permission_classes


def test_regular_group_member_cannot_hard_delete_own_seen_notification(
    user: User,
    group: Group,
    notification: Notification,
):
    """Group visibility permits personal actions, not administrative deletion."""
    user.groups.add(group)
    notification.group.add(group)
    notification.mark_as_seen(user)
    url = reverse("activities-delete-notification", kwargs={"pk": notification.pk})

    response = _client(user).delete(url)

    assert response.status_code == 403
    assert Notification.objects.filter(pk=notification.pk).exists()


def test_regular_group_member_cannot_hard_delete_all_activities(
    user: User,
    group: Group,
    notification: Notification,
):
    """Bulk permanent deletion must also enforce the action-level admin guard."""
    user.groups.add(group)
    notification.group.add(group)
    notification.mark_as_seen(user)

    response = _client(user).delete(reverse("activities-delete-activities"))

    assert response.status_code == 403
    assert Notification.objects.filter(pk=notification.pk).exists()


def test_staff_member_can_hard_delete_own_seen_group_notification(
    admin_user: User,
    group: Group,
    notification: Notification,
):
    """Staff still needs personal visibility and read state on this endpoint."""
    admin_user.groups.add(group)
    notification.group.add(group)
    notification.mark_as_seen(admin_user)

    response = _client(admin_user).delete(
        reverse("activities-delete-notification", kwargs={"pk": notification.pk})
    )

    assert response.status_code == 204
    assert not Notification.objects.filter(pk=notification.pk).exists()


def test_configured_extra_permission_applies_to_admin_action(
    monkeypatch,
    admin_user: User,
    notification: Notification,
):
    """Action-specific permissions cannot replace project-wide restrictions."""
    notification.recipient.add(admin_user)
    notification.mark_as_seen(admin_user)
    monkeypatch.setattr(config, "api_extra_permission_class", DenyAll)

    response = _client(admin_user).delete(
        reverse("activities-delete-notification", kwargs={"pk": notification.pk})
    )

    assert response.status_code == 403
    assert Notification.objects.filter(pk=notification.pk).exists()
