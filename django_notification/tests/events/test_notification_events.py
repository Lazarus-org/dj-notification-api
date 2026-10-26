"""Regression coverage for best-effort, post-commit lifecycle events."""

import pytest
from django.db import transaction

from django_notification.events import (
    NotificationEvent,
    NotificationEventKind,
    notification_event,
)
from django_notification.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def received_events():
    """Capture public events and disconnect the receiver after each test."""
    events = []

    def receiver(sender, event, **kwargs):
        assert sender is Notification
        assert isinstance(event, NotificationEvent)
        events.append(event)

    notification_event.connect(receiver, weak=False)
    try:
        yield events
    finally:
        notification_event.disconnect(receiver)


def test_created_event_fires_only_after_commit(
    user, received_events, django_capture_on_commit_callbacks
):
    """Nested atomic commits must not dispatch before the outer commit."""
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with transaction.atomic():
            item = Notification.objects.create_notification(
                actor=user, verb="Created", recipients=[user], is_sent=True
            )
            assert received_events == []
        assert received_events == []
    assert len(callbacks) == 1
    assert len(received_events) == 1
    event = received_events[0]
    assert event.kind == NotificationEventKind.CREATED
    assert event.notification_id == item.pk
    assert event.is_sent is True
    assert event.user_id is None
    assert not hasattr(event, "data")
    assert not hasattr(event, "recipients")


def test_rollback_discards_created_event(
    user, received_events, django_capture_on_commit_callbacks
):
    """A rolled-back create must not emit a notification."""
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError, match="rollback"):
            with transaction.atomic():
                Notification.objects.create_notification(
                    actor=user, verb="Rollback", recipients=[user]
                )
                raise RuntimeError("rollback")
    assert callbacks == []
    assert received_events == []


def test_retry_does_not_republish_created_event(
    user, received_events, django_capture_on_commit_callbacks
):
    """Idempotency reuse must not produce duplicate creation events."""
    with django_capture_on_commit_callbacks(execute=True):
        first = Notification.objects.create_notification(
            actor=user,
            verb="Same",
            recipients=[user],
            idempotency_key="test:created:1",
            is_sent=True,
        )
        second = Notification.objects.create_notification(
            actor=user,
            verb="Same",
            recipients=[user],
            idempotency_key="test:created:1",
            is_sent=True,
        )
    assert first.pk == second.pk
    assert [event.kind for event in received_events] == [NotificationEventKind.CREATED]


def test_read_and_clear_emit_only_real_single_state_changes(
    user, group, received_events, django_capture_on_commit_callbacks
):
    """Group members have personal state; sequential repeats are silent."""
    user.groups.add(group)
    with django_capture_on_commit_callbacks(execute=True):
        item = Notification.objects.create_notification(
            actor=user,
            verb="Group",
            groups=[group],
            is_sent=True,
        )
        assert Notification.objects.set_seen(user, item.pk, seen=True) is True
        assert Notification.objects.set_seen(user, item.pk, seen=True) is False
        assert Notification.objects.set_seen(user, item.pk, seen=False) is True
        assert Notification.objects.set_seen(user, item.pk, seen=False) is False
        assert Notification.objects.set_seen(user, item.pk, seen=True) is True
        Notification.objects.delete_notification(item.pk, recipient=user)
    assert [event.kind for event in received_events] == [
        NotificationEventKind.CREATED,
        NotificationEventKind.SEEN,
        NotificationEventKind.UNSEEN,
        NotificationEventKind.SEEN,
        NotificationEventKind.CLEARED,
    ]
    assert all(event.user_id == user.pk for event in received_events[1:])


def test_legacy_mark_as_seen_produces_one_state_event(
    user, received_events, django_capture_on_commit_callbacks
):
    """Old model helper and new API must share their event semantics."""
    with django_capture_on_commit_callbacks(execute=True):
        item = Notification.objects.create_notification(
            actor=user, verb="Legacy", recipients=[user], is_sent=True
        )
        item.mark_as_seen(user)
        item.mark_as_seen(user)
    assert [event.kind for event in received_events] == [
        NotificationEventKind.CREATED,
        NotificationEventKind.SEEN,
    ]


def test_bulk_actions_emit_aggregates_without_recipient_ids(
    user, received_events, django_capture_on_commit_callbacks
):
    """Bulk notifications expose counts instead of an unbounded ID list."""
    with django_capture_on_commit_callbacks(execute=True):
        items = [
            Notification.objects.create_notification(
                actor=user, verb=str(i), recipients=[user], is_sent=True
            )
            for i in range(3)
        ]
        ids = [item.pk for item in items]
        assert Notification.objects.set_many_seen(user, ids, seen=True) == 3
        assert Notification.objects.set_many_seen(user, ids, seen=True) == 3
        assert Notification.objects.clear_selected(user, ids) == 3
    seen = [
        event for event in received_events if event.kind == NotificationEventKind.SEEN
    ]
    cleared = [
        event
        for event in received_events
        if event.kind == NotificationEventKind.CLEARED
    ]
    assert len(seen) == len(cleared) == 1
    assert seen[0].batch and seen[0].affected_count == 3
    assert cleared[0].batch and cleared[0].affected_count == 3
    assert seen[0].notification_id is None
    assert cleared[0].notification_id is None


def test_updated_sent_and_hard_deleted_events(
    user, received_events, django_capture_on_commit_callbacks
):
    """Manager update, bulk send and hard deletion provide stable metadata."""
    with django_capture_on_commit_callbacks(execute=True):
        item = Notification.objects.create_notification(
            actor=user, verb="Initial", recipients=[user]
        )
        Notification.objects.update_notification(item.pk, public=False)
        Notification.objects.update_notification(item.pk, public=False)
        assert Notification.objects.mark_all_as_sent(recipients=[user]) == 1
        assert Notification.objects.mark_all_as_sent(recipients=[user]) == 0
        Notification.objects.delete_notification(item.pk, soft_delete=False)
    assert [event.kind for event in received_events] == [
        NotificationEventKind.CREATED,
        NotificationEventKind.UPDATED,
        NotificationEventKind.SENT,
        NotificationEventKind.SENT,
        NotificationEventKind.HARD_DELETED,
    ]
    assert received_events[1].fields == ("public",)
    assert received_events[2].notification_id == item.pk
    assert not received_events[2].batch
    assert received_events[3].batch
    assert received_events[4].notification_id == item.pk


def test_legacy_helper_keeps_unsent_compatibility(
    user, received_events, django_capture_on_commit_callbacks
):
    """Event integration must not tighten the historical model helper scope."""
    item = Notification.objects.create(verb="Draft", actor=user, is_sent=False)
    item.recipient.add(user)
    with django_capture_on_commit_callbacks(execute=True):
        item.mark_as_seen(user)
    assert [event.kind for event in received_events] == [NotificationEventKind.SEEN]


def test_draft_to_sent_emits_individual_sent_event(
    user, received_events, django_capture_on_commit_callbacks
):
    """Converting a draft to a delivered notification is observable."""
    with django_capture_on_commit_callbacks(execute=True):
        item = Notification.objects.create_notification(
            actor=user, verb="Draft", recipients=[user], is_sent=False
        )
        Notification.objects.update_notification(item.pk, is_sent=True)
    assert [event.kind for event in received_events] == [
        NotificationEventKind.CREATED,
        NotificationEventKind.UPDATED,
        NotificationEventKind.SENT,
    ]
    assert received_events[-1].notification_id == item.pk
    assert not received_events[-1].batch


def test_receiver_failure_does_not_block_other_receivers(
    user, received_events, django_capture_on_commit_callbacks, caplog
):
    """The event channel is best-effort and cannot roll back committed writes."""

    def broken_receiver(sender, event, **kwargs):
        raise RuntimeError("private details must not be logged")

    notification_event.connect(broken_receiver, weak=False)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            item = Notification.objects.create_notification(
                actor=user, verb="Error", recipients=[user]
            )
        assert Notification.objects.filter(pk=item.pk).exists()
        assert len(received_events) == 1
        assert "private details must not be logged" not in caplog.text
        assert all(record.exc_info is None for record in caplog.records)
    finally:
        notification_event.disconnect(broken_receiver)
