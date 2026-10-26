"""Regression coverage for opt-in event identity and time-window coalescing."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.utils import timezone

from django_notification.models import Notification, NotificationCreationKey
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.notification_creation_key import CreationKeyKind
from django_notification.services import notification as lifecycle_module

pytestmark = pytest.mark.django_db


def create(actor, **kwargs):
    """Create a sent notification with a stable default event payload."""
    return Notification.objects.create_notification(
        actor=actor, verb="order ready", is_sent=True, **kwargs
    )


def test_unkeyed_creation_retains_existing_behavior(user: User) -> None:
    """No key means every call creates a new notification."""
    first = create(user, recipients=[user])
    second = create(user, recipients=[user])
    assert first.pk != second.pk
    assert NotificationCreationKey.objects.count() == 0


def test_identical_idempotent_retries_reuse_the_original_notification(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """Order/duplicates of target collections do not change event identity."""
    first = create(
        user,
        recipients=[user, another_user],
        groups=[group],
        idempotency_key="orders:ready:123",
        description="Your order is ready",
        data={"b": 2, "a": 1},
    )
    repeat = create(
        user,
        recipients=(x for x in [another_user, user, user]),
        groups=Group.objects.filter(pk=group.pk),
        idempotency_key="orders:ready:123",
        description="Your order is ready",
        data={"a": 1, "b": 2},
    )
    assert first.pk == repeat.pk
    assert Notification.objects.count() == 1
    assert first.recipient.count() == 2
    assert NotificationCreationKey.objects.get().request_fingerprint


def test_idempotency_key_cannot_be_reused_with_different_content(
    user: User,
    another_user: User,
) -> None:
    """A conflicting retry never silently returns another payload."""
    first = create(user, recipients=[user], idempotency_key="events:key-1")
    with pytest.raises(ValueError, match="different event"):
        create(
            user,
            recipients=[another_user],
            idempotency_key="events:key-1",
        )
    with pytest.raises(ValueError, match="different event"):
        create(another_user, recipients=[user], idempotency_key="events:key-1")
    assert Notification.objects.count() == 1
    assert first.recipient.filter(pk=user.pk).exists()


def test_idempotency_survives_mutable_notification_state(
    user: User,
) -> None:
    """Subsequent read state and sent updates do not alter retry identity."""
    first = Notification.objects.create_notification(
        actor=user,
        verb="change",
        recipients=[user],
        idempotency_key="updates:42",
    )
    first.is_sent = True
    first.save(update_fields=["is_sent"])
    repeat = Notification.objects.create_notification(
        actor=user,
        verb="change",
        recipients=[user],
        idempotency_key="updates:42",
    )
    assert repeat.pk == first.pk
    assert repeat.is_sent is True


def test_idempotent_snapshot_is_not_recomputed_on_retry(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """A retry after membership changes preserves the original frozen audience."""
    user.groups.add(group)
    first = create(
        user,
        groups=[group],
        group_audience_mode=GroupAudienceMode.SNAPSHOT,
        idempotency_key="announcements:1",
    )
    user.groups.remove(group)
    another_user.groups.add(group)
    repeat = create(
        user,
        groups=[group],
        group_audience_mode=GroupAudienceMode.SNAPSHOT,
        idempotency_key="announcements:1",
    )
    assert repeat.pk == first.pk
    assert set(first.recipient.values_list("pk", flat=True)) == {user.pk}
    assert Notification.objects.visible_to(user).filter(pk=first.pk).exists()
    assert not Notification.objects.visible_to(another_user).exists()


def test_deduplication_coalesces_within_fixed_window(user: User) -> None:
    """Coalescing allows content changes but does not extend the window."""
    window = timedelta(minutes=10)
    first = create(
        user,
        recipients=user,
        deduplication_key="alerts:cpu:host-1",
        deduplication_window=window,
        description="First spike",
    )
    claim = NotificationCreationKey.objects.get(kind=CreationKeyKind.DEDUPLICATION)
    original_expiry = claim.expires_at
    repeat = create(
        user,
        recipients=[user],
        deduplication_key="alerts:cpu:host-1",
        deduplication_window=timedelta(minutes=20),
        description="Another spike",
    )
    claim.refresh_from_db()
    assert repeat.pk == first.pk
    assert claim.expires_at == original_expiry
    assert Notification.objects.count() == 1


def test_deduplication_creates_a_new_event_after_expiry(user: User) -> None:
    """Expired claims are atomically replaced, keeping previous events."""
    params = {
        "recipients": [user],
        "deduplication_key": "alerts:storage:host-2",
        "deduplication_window": timedelta(minutes=2),
    }
    first = create(user, **params)
    claim = NotificationCreationKey.objects.get()
    claim.expires_at = timezone.now() - timedelta(seconds=1)
    claim.save(update_fields=["expires_at"])
    second = create(user, **params)
    claim.refresh_from_db()
    assert second.pk != first.pk
    assert claim.notification_id == second.pk
    assert claim.expires_at > timezone.now()
    assert Notification.objects.count() == 2
    assert NotificationCreationKey.objects.count() == 1


def test_same_dedup_key_cannot_merge_different_audiences(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """Avoid cross-actor and cross-recipient collision information leaks."""
    params = {
        "deduplication_key": "shared-key",
        "deduplication_window": timedelta(minutes=5),
    }
    create(user, recipients=[user], **params)
    with pytest.raises(ValueError, match="different audience"):
        create(user, recipients=[another_user], **params)
    with pytest.raises(ValueError, match="different audience"):
        create(another_user, recipients=[user], **params)
    with pytest.raises(ValueError, match="different audience"):
        create(user, groups=[group], **params)
    assert Notification.objects.count() == 1


def test_different_keys_and_kinds_are_independent(user: User) -> None:
    """Idempotency and deduplication keys occupy different namespaces."""
    a = create(user, idempotency_key="evt:one")
    b = create(user, idempotency_key="evt:two")
    c = create(
        user,
        deduplication_key="evt:one",
        deduplication_window=timedelta(seconds=60),
    )
    assert len({a.pk, b.pk, c.pk}) == 3
    assert NotificationCreationKey.objects.count() == 3


@pytest.mark.parametrize("key", ["", "   ", " leading", "trailing ", "x" * 201, 42])
def test_invalid_idempotency_keys_fail_before_writes(user: User, key):
    """Blank, ambiguous and oversized keys cannot occupy the key table."""
    with pytest.raises(ValueError, match="Creation keys"):
        create(user, idempotency_key=key)
    assert not Notification.objects.exists()
    assert not NotificationCreationKey.objects.exists()


@pytest.mark.parametrize("window", [None, timedelta(0), timedelta(seconds=-1), 60])
def test_invalid_deduplication_window_fails_before_writes(user: User, window):
    """A deduplication key must have a positive timedelta window."""
    with pytest.raises(ValueError, match="positive timedelta"):
        create(user, deduplication_key="event:one", deduplication_window=window)
    assert not Notification.objects.exists()


def test_creation_modes_are_mutually_exclusive(user: User) -> None:
    """Invalid combinations cannot accidentally coalesce disparate events."""
    with pytest.raises(ValueError, match="not both"):
        create(
            user,
            idempotency_key="a",
            deduplication_key="b",
            deduplication_window=timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="key is required"):
        create(user, deduplication_window=timedelta(minutes=1))
    assert not NotificationCreationKey.objects.exists()


def test_creation_claim_and_recipient_writes_roll_back_on_failure(
    monkeypatch,
    user: User,
    group: Group,
) -> None:
    """A failed snapshot leaves no notification or reserved creation key."""

    def failure(*args, **kwargs):
        raise RuntimeError("recipient snapshot failed")

    monkeypatch.setattr(
        lifecycle_module.NotificationLifecycleService,
        "_snapshot_group_recipients",
        failure,
    )
    with pytest.raises(RuntimeError, match="recipient snapshot failed"):
        create(
            user,
            groups=[group],
            group_audience_mode=GroupAudienceMode.SNAPSHOT,
            idempotency_key="snapshots:failed",
        )
    assert not Notification.objects.exists()
    assert not NotificationCreationKey.objects.exists()


def test_database_rejects_duplicate_claims(user: User) -> None:
    """The actual unique constraint is the concurrency correctness boundary."""
    create(user, idempotency_key="events:unique")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificationCreationKey.objects.create(
                kind=CreationKeyKind.IDEMPOTENCY,
                key="events:unique",
            )
    assert NotificationCreationKey.objects.count() == 1


def test_hard_delete_releases_creation_key(user: User) -> None:
    """Idempotency is retained only while the original notification exists."""
    first = create(user, idempotency_key="temp:event")
    original_pk = first.pk
    first.delete()
    assert not NotificationCreationKey.objects.exists()
    second = create(user, idempotency_key="temp:event")
    assert second.pk != original_pk


@pytest.mark.django_db(transaction=True)
def test_postgres_concurrent_creators_reuse_one_notification(user: User) -> None:
    """PostgreSQL unique claims serialize simultaneous real transactions."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("Concurrency gate requires PostgreSQL row locking")
    ready = Barrier(2)

    def create_once():
        ready.wait(timeout=10)
        result = create(
            user,
            recipients=[user],
            idempotency_key="races:one-event",
        )
        return result.pk

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(create_once)
        b = pool.submit(create_once)
        assert a.result(timeout=20) == b.result(timeout=20)
    assert Notification.objects.count() == 1
    assert NotificationCreationKey.objects.count() == 1
