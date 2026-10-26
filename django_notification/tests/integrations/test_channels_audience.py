"""Audience regression tests that do not require Channels to be installed."""

import pytest
from django.utils import timezone

from django_notification.integrations.channels.audience import (
    eligible_audience,
    notification_visible,
)
from django_notification.integrations.channels.dispatcher import user_channel_group
from django_notification.models import (
    Notification,
    NotificationCategory,
    NotificationPreference,
)
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)

pytestmark = pytest.mark.django_db


def create(actor, **kwargs):
    """Create a ready notification using only configured package defaults."""
    return Notification.objects.create_notification(
        actor=actor, verb="Ready", is_sent=True, **kwargs
    )


def recipients(item):
    """Return all users eligible for a push of one notification."""
    return set(eligible_audience(item.pk, "default"))


def test_group_and_direct_audience_no_duplicates(user, another_user, group):
    """Overlapping target edges must dispatch once to each eligible user."""
    user.groups.add(group)
    item = create(user, recipients=[user, another_user], groups=[group])
    assert recipients(item) == {user.pk, another_user.pk}
    user.groups.remove(group)
    assert recipients(item) == {user.pk, another_user.pk}


def test_group_membership_changes_at_dispatch(user, another_user, group):
    """New dynamic members receive events, former members do not."""
    user.groups.add(group)
    item = create(user, groups=[group])
    assert recipients(item) == {user.pk}
    user.groups.remove(group)
    another_user.groups.add(group)
    assert recipients(item) == {another_user.pk}
    assert notification_visible(user.pk, item.pk, "default") == (True, False)


def test_snapshot_membership_is_fixed(user, another_user, group):
    """Snapshot recipients remain eligible after leaving the Django group."""
    user.groups.add(group)
    item = create(user, groups=[group], group_audience_mode=GroupAudienceMode.SNAPSHOT)
    user.groups.remove(group)
    another_user.groups.add(group)
    assert recipients(item) == {user.pk}


def test_inactive_and_unsent_or_expired_notifications_are_excluded(user):
    """Do not send inactive users or notifications outside their live window."""
    item = create(user, recipients=[user])
    assert recipients(item) == {user.pk}
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert recipients(item) == set()
    assert notification_visible(user.pk, item.pk, "default") == (False, False)
    user.is_active = True
    user.save(update_fields=["is_active"])
    Notification.objects.filter(pk=item.pk).update(expires_at=timezone.now())
    assert recipients(item) == set()


def test_opt_out_and_soft_deletion_are_respected(user, another_user):
    """Preferences and per-user clears must limit dispatch independently."""
    category = NotificationCategory.objects.create(
        slug="ws-topic", name="WebSocket topic"
    )
    item = create(user, recipients=[user, another_user], category=category.slug)
    NotificationPreference.objects.create(user=user, category=category, enabled=False)
    assert recipients(item) == {another_user.pk}
    category.is_mandatory = True
    category.save(update_fields=["is_mandatory"])
    assert recipients(item) == {user.pk, another_user.pk}
    Notification.objects.delete_notification(item.pk, recipient=user)
    assert recipients(item) == {another_user.pk}


def test_channel_group_name_never_exposes_primary_key(settings):
    """Names must be deterministic, opaque and accepted by Channels backends."""
    settings.SECRET_KEY = "specific-test-key"
    first = user_channel_group("user/with:unsafe*characters", "default")
    second = user_channel_group("user/with:unsafe*characters", "other")
    assert first.startswith("djnotify.user.")
    assert "unsafe" not in first
    assert len(first) <= 100
    assert first != second
    assert first == user_channel_group("user/with:unsafe*characters", "default")
