"""Outbox publishing, lease recovery, retries and explicit operator recovery."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from django_notification.events import NotificationEvent, NotificationEventKind
from django_notification.events import notification_event, publish_notification_event
from django_notification.models import Notification, NotificationOutboxEvent
from django_notification.models.notification_outbox_event import OutboxStatus
from django_notification.outbox import OutboxDeliveryService

pytestmark = pytest.mark.django_db
OUTBOX = override_settings(DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox")


@pytest.fixture
def handler():
    """Provide a receiver and reliably disconnect it after every test."""
    received = []

    def receiver(sender, event, outbox_event_id=None, **kwargs):
        received.append((sender, event, outbox_event_id))

    notification_event.connect(receiver, weak=False)
    try:
        yield received
    finally:
        notification_event.disconnect(receiver)


@OUTBOX
def test_creation_and_rollback_share_the_notification_transaction(user):
    """Rolled-back business changes never leave a deliverable event."""
    with pytest.raises(RuntimeError, match="rollback"):
        with transaction.atomic():
            Notification.objects.create_notification(
                actor=user, verb="Rollback", recipients=[user], is_sent=True
            )
            assert NotificationOutboxEvent.objects.count() == 1
            raise RuntimeError("rollback")
    assert NotificationOutboxEvent.objects.count() == 0


@OUTBOX
def test_event_survives_commit_and_reaches_receiver_once(user, handler):
    """Persist first; deliver later using a worker, not an on_commit signal."""
    with transaction.atomic():
        item = Notification.objects.create_notification(
            actor=user, verb="Durable", recipients=[user], is_sent=True
        )
    assert handler == []
    row = NotificationOutboxEvent.objects.get()
    assert row.kind == NotificationEventKind.CREATED
    assert row.payload["notification_id"] == item.pk
    assert "verb" not in row.payload
    service = OutboxDeliveryService()
    assert service.process_next() == "delivered"
    assert service.process_next() == "empty"
    row.refresh_from_db()
    assert row.status == OutboxStatus.DELIVERED
    assert row.attempts == 1
    assert handler[0][1].notification_id == item.pk
    assert handler[0][2] == row.pk


@OUTBOX
def test_idempotent_retry_does_not_create_a_second_event(user):
    """An identical creation retry does not republish the logical event."""
    args = dict(
        actor=user,
        verb="Same",
        recipients=[user],
        is_sent=True,
        idempotency_key="outbox:creation:one",
    )
    first = Notification.objects.create_notification(**args)
    second = Notification.objects.create_notification(**args)
    assert first.pk == second.pk
    assert NotificationOutboxEvent.objects.count() == 1


@OUTBOX
def test_no_registered_receiver_must_not_acknowledge_delivery(user):
    """Missing worker registrations must not cause silent event loss."""
    Notification.objects.create_notification(actor=user, verb="No sink")
    service = OutboxDeliveryService(retry_base_seconds=1)
    with patch.object(notification_event, "has_listeners", return_value=False):
        assert service.process_next() == "retry"
    row = NotificationOutboxEvent.objects.get()
    assert row.status == OutboxStatus.PENDING
    assert row.attempts == 1
    assert row.delivered_at is None


@OUTBOX
def test_receiver_error_causes_backoff_then_replay(user):
    """A temporary receiver failure is retried with the same event ID."""
    Notification.objects.create_notification(actor=user, verb="Retry")
    calls = []

    def flaky(sender, event, outbox_event_id=None, **kwargs):
        calls.append(outbox_event_id)
        if len(calls) == 1:
            raise RuntimeError("deliberately private message")

    notification_event.connect(flaky, weak=False)
    try:
        service = OutboxDeliveryService(retry_base_seconds=5, retry_max_seconds=10)
        assert service.process_next() == "retry"
        row = NotificationOutboxEvent.objects.get()
        assert row.status == OutboxStatus.PENDING
        assert row.attempts == 1
        assert service.process_next() == "empty"
        NotificationOutboxEvent.objects.filter(pk=row.pk).update(
            available_at=timezone.now() - timedelta(seconds=1)
        )
        assert service.process_next() == "delivered"
        assert calls == [row.pk, row.pk]
    finally:
        notification_event.disconnect(flaky)


@OUTBOX
def test_crashed_worker_lease_is_recovered(user, handler):
    """Other workers can take an expired claim, but not a live one."""
    Notification.objects.create_notification(actor=user, verb="Claim")
    worker = OutboxDeliveryService()
    claimed = worker.claim_one()
    assert claimed is not None
    assert OutboxDeliveryService().claim_one() is None
    NotificationOutboxEvent.objects.filter(pk=claimed.pk).update(
        leased_until=timezone.now() - timedelta(seconds=1)
    )
    assert worker.process_next() == "delivered"
    row = NotificationOutboxEvent.objects.get()
    assert row.attempts == 2
    assert len(handler) == 1
    assert worker._acknowledge(claimed) is False


@OUTBOX
def test_exhausted_failures_require_explicit_requeue(user):
    """Terminal failures remain inspectable and operator-replayable."""
    Notification.objects.create_notification(actor=user, verb="Failure")
    service = OutboxDeliveryService(max_attempts=2, retry_base_seconds=1)
    with patch.object(notification_event, "has_listeners", return_value=False):
        assert service.process_next() == "retry"
        row = NotificationOutboxEvent.objects.get()
        NotificationOutboxEvent.objects.filter(pk=row.pk).update(
            available_at=timezone.now() - timedelta(seconds=1)
        )
        assert service.process_next() == "failed"
    row.refresh_from_db()
    assert row.status == OutboxStatus.FAILED
    assert row.attempts == 2
    assert service.process_next() == "empty"
    call_command("requeue_notification_outbox", str(row.pk))
    row.refresh_from_db()
    assert row.status == OutboxStatus.PENDING
    assert row.attempts == 0


@OUTBOX
def test_stale_final_lease_is_marked_failed(user):
    """An abandoned last attempt cannot remain stuck in PROCESSING."""
    Notification.objects.create_notification(actor=user, verb="Abandoned")
    service = OutboxDeliveryService(max_attempts=1)
    claim = service.claim_one()
    NotificationOutboxEvent.objects.filter(pk=claim.pk).update(
        leased_until=timezone.now() - timedelta(seconds=1)
    )
    assert service.claim_one() is None
    assert NotificationOutboxEvent.objects.get().status == OutboxStatus.FAILED


@OUTBOX
def test_read_state_and_hard_deletion_events_survive(user, handler):
    """Outbox rows don't cascade away when Notification is hard deleted."""
    item = Notification.objects.create_notification(
        actor=user, verb="Deleted", recipients=[user], is_sent=True
    )
    assert Notification.objects.set_seen(user, item.pk, seen=True)
    Notification.objects.delete_notification(item.pk, soft_delete=False)
    assert list(NotificationOutboxEvent.objects.values_list("kind", flat=True)) == [
        NotificationEventKind.CREATED,
        NotificationEventKind.SEEN,
        NotificationEventKind.HARD_DELETED,
    ]
    service = OutboxDeliveryService()
    assert service.process_batch(limit=10)["delivered"] == 3
    assert [event.kind for _, event, _ in handler] == [
        NotificationEventKind.CREATED,
        NotificationEventKind.SEEN,
        NotificationEventKind.HARD_DELETED,
    ]


@OUTBOX
def test_publishing_without_transaction_fails_closed():
    """Prevent standalone callers from claiming a nonexistent atomic guarantee."""
    # pytest-django's db fixture may wrap a test in an outer transaction,
    # so override the connection flag to model an autocommit caller.
    from django.db import connections

    event = NotificationEvent(kind=NotificationEventKind.CREATED, database="default")
    connection = connections["default"]
    with patch.object(connection, "in_atomic_block", False):
        with pytest.raises(RuntimeError, match="active transaction"):
            publish_notification_event(event)


@OUTBOX
def test_delivered_rows_only_can_be_pruned(user, handler):
    """Cleanup never removes pending, failed or leased delivery intent."""
    Notification.objects.create_notification(actor=user, verb="Delivered")
    Notification.objects.create_notification(actor=user, verb="Pending")
    assert OutboxDeliveryService().process_next() == "delivered"
    delivered = NotificationOutboxEvent.objects.filter(
        status=OutboxStatus.DELIVERED
    ).get()
    NotificationOutboxEvent.objects.filter(pk=delivered.pk).update(
        delivered_at=timezone.now() - timedelta(days=40)
    )
    assert NotificationOutboxEvent.objects.count() == 2
    call_command("prune_notification_outbox", "--older-than-days=30")
    assert NotificationOutboxEvent.objects.count() == 2
    call_command("prune_notification_outbox", "--execute", "--older-than-days=30")
    assert NotificationOutboxEvent.objects.count() == 1
    assert NotificationOutboxEvent.objects.get().status == OutboxStatus.PENDING


@OUTBOX
def test_operator_cannot_requeue_delivered_events(user, handler):
    """Manual replay only applies to terminal failures."""
    Notification.objects.create_notification(actor=user, verb="Once")
    assert OutboxDeliveryService().process_next() == "delivered"
    event = NotificationOutboxEvent.objects.get()
    call_command("requeue_notification_outbox", str(event.pk))
    event.refresh_from_db()
    assert event.status == OutboxStatus.DELIVERED
    assert OutboxDeliveryService().process_next() == "empty"


def test_invalid_outbox_mode_system_check(settings):
    """Invalid deployment mode must be rejected during Django checks."""
    from django_notification.settings.checks import check_notification_settings

    settings.DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "unknown"
    errors = check_notification_settings(None)
    assert any(error.id == "django_notification.E001" for error in errors)
