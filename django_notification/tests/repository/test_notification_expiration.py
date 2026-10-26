"""Notification expiry boundaries, group policies, and state isolation."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.http import Http404
from django.utils import timezone

from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationSeen,
)
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)

pytestmark = pytest.mark.django_db


def create(user, **kwargs):
    """Create a sent notification through the public lifecycle manager."""
    return Notification.objects.create_notification(
        actor=user, verb="notification expiry test", is_sent=True, **kwargs
    )


def test_expiration_boundaries_and_non_expiring_default(user: User):
    """The exact expires_at instant is expired; null always remains active."""
    instant = timezone.now()
    permanent = create(user, recipients=[user])
    boundary = create(user, recipients=[user], expires_at=instant)
    future = create(user, recipients=[user], expires_at=instant + timedelta(seconds=1))
    active = Notification.objects.active_at(instant)
    expired = Notification.objects.expired_at(instant)
    assert set(active.values_list("pk", flat=True)) == {permanent.pk, future.pk}
    assert list(expired.values_list("pk", flat=True)) == [boundary.pk]
    assert Notification.objects.count() == 3  # Expiration is not deletion.


def test_personal_legacy_queries_hide_expired_direct_and_group_records(
    user: User,
    another_user: User,
    group: Group,
):
    """All personal selectors agree on expiration for direct/group visibility."""
    user.groups.add(group)
    past = timezone.now() - timedelta(minutes=1)
    direct = create(user, recipients=[user], expires_at=past)
    group_only = create(user, groups=[group], expires_at=past)
    live_group = create(user, groups=[group])
    assert set(Notification.objects.visible_to(user).values_list("pk", flat=True)) == {
        direct.pk,
        group_only.pk,
        live_group.pk,
    }  # Target authorization remains independently composable.
    assert list(
        Notification.objects.unseen(unseen_by=user).values_list("pk", flat=True)
    ) == [live_group.pk]
    assert Notification.objects.sent(exclude_deleted_by=user).count() == 1
    assert not Notification.objects.unseen(unseen_by=another_user).exists()


def test_per_user_state_changes_reject_expired_records_atomically(
    user: User,
):
    """No single or mixed bulk call may mutate expired notification state."""
    expired = create(
        user,
        recipients=[user],
        expires_at=timezone.now() - timedelta(seconds=5),
    )
    active = create(user, recipients=[user])
    with pytest.raises(Http404):
        Notification.objects.set_seen(user, expired.pk, True)
    with pytest.raises(Http404):
        Notification.objects.set_many_seen(user, [active.pk, expired.pk], True)
    assert not NotificationSeen.objects.exists()
    assert Notification.objects.mark_all_as_seen(user) == 1
    assert NotificationSeen.objects.filter(notification=active, user=user).exists()
    assert not NotificationSeen.objects.filter(notification=expired).exists()
    with pytest.raises(PermissionError):
        expired.mark_as_seen(user)
    with pytest.raises(Http404):
        Notification.objects.delete_notification(expired.pk, recipient=user)
    assert not DeletedNotification.objects.exists()


def test_expired_read_activities_remain_stored_but_cannot_be_cleared(user: User):
    """Historical read rows survive expiration until explicit global cleanup."""
    item = create(user, recipients=[user])
    item.mark_as_seen(user)
    Notification.objects.filter(pk=item.pk).update(
        expires_at=timezone.now() - timedelta(seconds=5)
    )
    assert NotificationSeen.objects.filter(notification=item, user=user).exists()
    assert not Notification.objects.seen(seen_by=user).exists()
    with pytest.raises(Http404):
        Notification.objects.clear_selected(user, [item.pk])
    Notification.objects.clear_all(user)
    assert not DeletedNotification.objects.exists()


def test_expiration_does_not_change_snapshot_group_audience(
    user: User,
    another_user: User,
    group: Group,
):
    """Snapshot membership still controls targeting, before and after expiry."""
    user.groups.add(group)
    item = create(
        user,
        groups=[group],
        group_audience_mode=GroupAudienceMode.SNAPSHOT,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    user.groups.remove(group)
    another_user.groups.add(group)
    assert Notification.objects.visible_to(user).active_at().filter(pk=item.pk).exists()
    assert not Notification.objects.visible_to(another_user).filter(pk=item.pk).exists()
    Notification.objects.filter(pk=item.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert not Notification.objects.visible_to(user).active_at().exists()
    assert item.recipient.filter(pk=user.pk).exists()


def test_idempotency_fingerprints_include_expiration(user: User):
    """Retry cannot silently change an original notification's TTL."""
    expiry = timezone.now() + timedelta(hours=1)
    kwargs = dict(recipients=[user], idempotency_key="ttl:event:1")
    original = create(user, expires_at=expiry, **kwargs)
    assert create(user, expires_at=expiry, **kwargs).pk == original.pk
    with pytest.raises(ValueError, match="different event"):
        create(user, expires_at=expiry + timedelta(hours=1), **kwargs)
    assert Notification.objects.count() == 1


def test_equivalent_timezone_instants_are_one_idempotent_event(user: User):
    """Offsets with the same instant yield the same request fingerprint."""
    from datetime import timezone as dt_timezone

    original_expiry = timezone.now() + timedelta(hours=1)
    shifted = original_expiry.astimezone(dt_timezone(timedelta(hours=3)))
    first = create(
        user,
        recipients=[user],
        expires_at=original_expiry,
        idempotency_key="ttl:same-instant",
    )
    second = create(
        user,
        recipients=[user],
        expires_at=shifted,
        idempotency_key="ttl:same-instant",
    )
    assert first.pk == second.pk


def test_creation_rejects_naive_expiry(user: User):
    """Reject timezone-naive and non-datetime API values before any writes."""
    from datetime import datetime

    for invalid in (datetime(2026, 2, 1, 0, 0), "2026-02-01T00:00:00Z"):
        with pytest.raises(ValueError, match="timezone-aware"):
            create(user, recipients=[user], expires_at=invalid)
    assert not Notification.objects.exists()


def test_deduplication_does_not_reuse_an_expired_notification(user: User):
    """A live key cannot suppress a new event if the previous item expired."""
    expiry = timezone.now() + timedelta(minutes=1)
    kwargs = dict(
        recipients=[user],
        deduplication_key="ttl:burst:1",
        deduplication_window=timedelta(hours=2),
    )
    first = create(user, expires_at=expiry, **kwargs)
    Notification.objects.filter(pk=first.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    second = create(user, expires_at=expiry, **kwargs)
    assert second.pk != first.pk
    assert Notification.objects.count() == 2


def test_existing_nonexpiring_notifications_keep_access(
    user: User,
    group: Group,
):
    """Old rows with null expiry remain eligible for group reads and state."""
    user.groups.add(group)
    item = create(user, groups=[group])
    assert item.expires_at is None
    assert Notification.objects.set_seen(user, item.pk, True)
    assert Notification.objects.seen(seen_by=user).filter(pk=item.pk).exists()
