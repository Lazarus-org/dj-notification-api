"""Real row-lock and transaction races; SQLite cannot establish these claims."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from django_notification.delivery.service import NotificationDeliveryService
from django_notification.models import (
    Notification,
    NotificationDelivery,
    NotificationDigest,
)
from django_notification.models.notification_outbox_event import NotificationOutboxEvent
from django_notification.outbox import OutboxDeliveryService

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Requires PostgreSQL row locks"
    ),
]


def parallel_calls(operation, workers=4):
    """Start workers together, each with its own database connection."""
    barrier = Barrier(workers)

    def run():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return operation()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run) for _ in range(workers)]
        return [future.result(timeout=20) for future in futures]


def test_outbox_claims_are_exclusive_and_skip_locked():
    rows = [
        NotificationOutboxEvent.objects.create(kind="notification.sent", payload={})
        for _ in range(5)
    ]
    with transaction.atomic():
        NotificationOutboxEvent.objects.select_for_update().get(pk=rows[0].pk)
        claimed = parallel_calls(lambda: OutboxDeliveryService().claim_one().pk)
    assert len(set(claimed)) == 4
    assert rows[0].pk not in claimed
    assert OutboxDeliveryService().claim_one().pk == rows[0].pk


def test_delivery_and_digest_claims_are_exclusive(user, settings):
    settings.DJANGO_NOTIFICATION_DELIVERY_BACKENDS = {
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
    item = Notification.objects.create_notification(
        actor=user, verb="Race", recipients=[user], is_sent=True
    )
    # Unique recipient/channel keys require different notifications per job.
    items = [item] + [
        Notification.objects.create_notification(
            actor=user, verb=str(i), recipients=[user], is_sent=True
        )
        for i in range(3)
    ]
    for item in items:
        NotificationDelivery.objects.create(
            notification=item, recipient=user, channel="email"
        )
    claimed = parallel_calls(lambda: NotificationDeliveryService().claim_one().pk)
    assert len(set(claimed)) == 4
    for i in range(4):
        NotificationDigest.objects.create(
            recipient=user,
            channel="email",
            scheduled_at=timezone.now() + timedelta(seconds=i),
        )
    claimed = parallel_calls(lambda: NotificationDeliveryService()._claim_digest().pk)
    assert len(set(claimed)) == 4


def test_creation_key_race_creates_one_notification(user, settings):
    settings.DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"
    user_id = user.pk

    def create():
        actor = get_user_model().objects.get(pk=user_id)
        return Notification.objects.create_notification(
            actor=actor,
            verb="Once",
            recipients=[actor],
            idempotency_key="concurrent:1",
        ).pk

    assert len(set(parallel_calls(create))) == 1
    assert Notification.objects.count() == 1
    assert NotificationOutboxEvent.objects.count() == 1


def test_concurrent_bulk_sends_emit_one_transition_per_row(user, settings):
    settings.DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"
    for i in range(5):
        Notification.objects.create_notification(
            actor=user, verb=str(i), recipients=[user]
        )
    NotificationOutboxEvent.objects.all().delete()
    counts = parallel_calls(lambda: Notification.objects.mark_all_as_sent())
    assert sum(counts) == 5
    assert NotificationOutboxEvent.objects.filter(payload__batch=False).count() == 5
    assert NotificationOutboxEvent.objects.filter(payload__batch=True).count() == 1
