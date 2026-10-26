"""Expired personal notifications do not leak through HTTP endpoints."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_notification.models import Notification, NotificationSeen
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_throttle(monkeypatch):
    """Eliminate rate limiting from focused API expiry assertions."""
    monkeypatch.setattr(config, "api_throttle_class", None)


def client(user):
    """Authenticate one user's in-app notification requests."""
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def make_notification(user, *, expires_at=None, recipients=None, groups=None):
    """Create a sent record without touching its read state."""
    return Notification.objects.create_notification(
        actor=user,
        verb="expiration api",
        is_sent=True,
        recipients=recipients,
        groups=groups,
        expires_at=expires_at,
    )


def test_expired_notifications_are_hidden_from_unread_and_summary(
    user: User,
    group: Group,
):
    """Expired direct and group rows are omitted from list and summary."""
    user.groups.add(group)
    old = timezone.now() - timedelta(minutes=1)
    make_notification(user, expires_at=old, recipients=[user])
    make_notification(user, expires_at=old, groups=[group])
    live = make_notification(user, groups=[group])
    api = client(user)
    response = api.get(reverse("notifications-list"))
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == live.pk
    assert api.get(reverse("notifications-summary")).data == {
        "total_count": 1,
        "read_count": 0,
        "unread_count": 1,
    }


def test_expired_notification_preview_detail_and_actions_return_404(user: User):
    """Expired IDs are uniformly indistinguishable from non-visible IDs."""
    expired = make_notification(
        user,
        recipients=[user],
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    api = client(user)
    for name in ("notifications-detail", "notifications-preview"):
        assert api.get(reverse(name, kwargs={"pk": expired.pk})).status_code == 404
    for name in ("notifications-mark-seen", "notifications-mark-unseen"):
        assert api.post(reverse(name, kwargs={"pk": expired.pk})).status_code == 404
    assert (
        api.post(
            reverse("notifications-bulk-mark-seen"),
            {"ids": [expired.pk]},
            format="json",
        ).status_code
        == 404
    )
    assert not NotificationSeen.objects.filter(notification=expired).exists()


def test_expired_activity_cannot_be_retrieved_or_deleted(user: User):
    """An old read-state record does not create an expired activity entry."""
    record = make_notification(user, recipients=[user])
    record.mark_as_seen(user)
    Notification.objects.filter(pk=record.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    api = client(user)
    assert api.get(reverse("activities-list")).data["count"] == 0
    assert (
        api.get(reverse("activities-detail", kwargs={"pk": record.pk})).status_code
        == 404
    )
    assert (
        api.delete(reverse("activities-detail", kwargs={"pk": record.pk})).status_code
        == 404
    )
    assert NotificationSeen.objects.filter(notification=record, user=user).exists()


def test_inbox_summary_follows_expiration_without_cleanup(user: User):
    """Counts reflect expiry as soon as the timestamp crosses the boundary."""
    item = make_notification(user, recipients=[user])
    item.mark_as_seen(user)
    api = client(user)
    assert api.get(reverse("notifications-summary")).data["read_count"] == 1
    Notification.objects.filter(pk=item.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert api.get(reverse("notifications-summary")).data == {
        "total_count": 0,
        "read_count": 0,
        "unread_count": 0,
    }
