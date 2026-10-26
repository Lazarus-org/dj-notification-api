"""Regression tests for transactional notification lifecycle services."""

import pytest
from django.db.models import QuerySet
from django.http import Http404

from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationSeen,
)
from django_notification.services import notification as lifecycle_module

pytestmark = pytest.mark.django_db


def _make_notifications(actor, number, *, sent=True):
    """Create a test feed with stable integer PKs for batching assertions."""
    return [
        Notification.objects.create(verb=f"event-{n}", actor=actor, is_sent=sent)
        for n in range(number)
    ]


def test_create_notification_assigns_single_targets_atomically(user, group):
    """Manager creation remains backward compatible for model targets."""
    created = Notification.objects.create_notification(
        verb="ready", actor=user, recipients=user, groups=group, is_sent=True
    )
    assert created.recipient.filter(pk=user.pk).exists()
    assert created.group.filter(pk=group.pk).exists()


def test_create_rolls_back_record_when_target_assignment_fails(user):
    """An invalid M2M target must not leave an unaddressed orphan row."""
    before = Notification.objects.count()
    with pytest.raises(TypeError):
        Notification.objects.create_notification(
            verb="invalid", actor=user, recipients=user, groups=[user]
        )
    assert Notification.objects.count() == before


def test_update_and_hard_delete_preserve_manager_contract(user):
    """Partial updates do not reset other fields; hard delete is explicit."""
    item = Notification.objects.create_notification(
        verb="start", actor=user, public=True, is_sent=True, data={"a": 1}
    )
    result = Notification.objects.update_notification(item.pk, public=False)
    assert result.pk == item.pk
    assert result.public is False
    assert result.data == {"a": 1}
    assert result.is_sent is True
    Notification.objects.delete_notification(item.pk, soft_delete=False)
    assert not Notification.objects.filter(pk=item.pk).exists()
    with pytest.raises(Http404):
        Notification.objects.delete_notification(item.pk, soft_delete=False)


def test_mark_sent_respects_explicit_empty_targets(user):
    """Explicit empty scope does not mutate the entire unsent set."""
    row = Notification.objects.create(verb="draft", actor=user, is_sent=False)
    row.recipient.add(user)
    assert Notification.objects.mark_all_as_sent(recipients=[]) == 0
    row.refresh_from_db()
    assert not row.is_sent
    assert Notification.objects.mark_all_as_sent(recipients=[user]) == 1
    assert Notification.objects.mark_all_as_sent(recipients=[user]) == 0
    row.refresh_from_db()
    assert row.is_sent


def test_seen_batches_cover_group_and_direct_once(monkeypatch, user, group):
    """Keyset processing includes group-only, direct and overlapping targets."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    user.groups.add(group)
    rows = _make_notifications(user, 7)
    for number, row in enumerate(rows):
        if number % 2 == 0:
            row.group.add(group)
        else:
            row.recipient.add(user)
    rows[0].recipient.add(user)  # Overlapping group and direct targets.
    other = Notification.objects.create(verb="foreign", actor=user, is_sent=True)
    assert Notification.objects.mark_all_as_seen(user) == 7
    assert NotificationSeen.objects.filter(user=user).count() == 7
    assert not NotificationSeen.objects.filter(notification=other).exists()
    assert Notification.objects.mark_all_as_seen(user) == 0


def test_bulk_mark_seen_preserves_each_users_state(monkeypatch, user, qs_user, group):
    """Marking a shared group event does not mark it for other group members."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    user.groups.add(group)
    qs_user.groups.add(group)
    item = Notification.objects.create(verb="shared", actor=user, is_sent=True)
    item.group.add(group)
    assert Notification.objects.mark_all_as_seen(user) == 1
    assert Notification.objects.mark_all_as_seen(qs_user) == 1
    assert NotificationSeen.objects.filter(notification=item).count() == 2
    assert Notification.objects.mark_all_as_seen(user) == 0


def test_clear_batches_only_seen_and_visible(monkeypatch, user, qs_user, group):
    """Clear is bounded, idempotent and isolated to the current recipient."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    user.groups.add(group)
    qs_user.groups.add(group)
    rows = _make_notifications(user, 7)
    for row in rows:
        row.group.add(group)
    assert Notification.objects.mark_all_as_seen(user) == 7
    assert Notification.objects.mark_all_as_seen(qs_user) == 7
    # One unread group event must not be cleared by user.
    unread = Notification.objects.create(verb="unread", actor=user, is_sent=True)
    unread.group.add(group)
    Notification.objects.clear_all(user)
    Notification.objects.clear_all(user)
    assert DeletedNotification.objects.filter(user=user).count() == 7
    assert not DeletedNotification.objects.filter(user=qs_user).exists()
    assert not DeletedNotification.objects.filter(notification=unread).exists()
    assert Notification.objects.filter(pk__in=[r.pk for r in rows]).count() == 7


def test_soft_delete_checks_group_visibility_and_repeated_delete(user, qs_user, group):
    """Unrelated users cannot erase someone else's group notification."""
    user.groups.add(group)
    row = Notification.objects.create(verb="group", actor=user, is_sent=True)
    row.group.add(group)
    with pytest.raises(Http404):
        Notification.objects.delete_notification(row.pk, recipient=qs_user)
    Notification.objects.delete_notification(row.pk, recipient=user)
    assert DeletedNotification.objects.filter(user=user, notification=row).count() == 1
    with pytest.raises(Http404):
        Notification.objects.delete_notification(row.pk, recipient=user)


def test_batch_mark_seen_rolls_back_all_chunks(monkeypatch, user):
    """An exception after one successful batch rolls back all previous batches."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    rows = _make_notifications(user, 5)
    for row in rows:
        row.recipient.add(user)
    original = QuerySet.bulk_create
    calls = 0

    def fail_second_chunk(queryset, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated later batch failure")
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "bulk_create", fail_second_chunk)
    with pytest.raises(RuntimeError, match="later batch"):
        Notification.objects.mark_all_as_seen(user)
    assert NotificationSeen.objects.filter(user=user).count() == 0


def test_batch_clear_rolls_back_all_chunks(monkeypatch, user):
    """Clear is one transaction even when multiple batches are written."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    rows = _make_notifications(user, 5)
    for row in rows:
        row.recipient.add(user)
    assert Notification.objects.mark_all_as_seen(user) == 5
    original = QuerySet.bulk_create
    calls = 0

    def fail_second_chunk(queryset, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated later batch failure")
        return original(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "bulk_create", fail_second_chunk)
    with pytest.raises(RuntimeError, match="later batch"):
        Notification.objects.clear_all(user)
    assert DeletedNotification.objects.filter(user=user).count() == 0


def test_filtered_queryset_mutation_is_deprecated_but_preserved(user):
    """Direct queryset mutation calls remain usable for older integrations."""
    row = Notification.objects.create(verb="legacy", actor=user, is_sent=False)
    with pytest.warns(DeprecationWarning):
        changed = Notification.objects.filter(pk=row.pk).mark_all_as_sent()
    assert changed == 1
    row.refresh_from_db()
    assert row.is_sent
