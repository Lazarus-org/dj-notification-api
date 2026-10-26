"""Bounded exhausted-lease recovery shared by outbox and delivery workers."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone

from django_notification._worker import (
    EXHAUSTED_SWEEP_LIMIT,
    retry_delay_seconds,
    validate_retry_settings,
)
from django_notification.delivery.service import NotificationDeliveryService
from django_notification.models.notification import Notification
from django_notification.models.notification_delivery import (
    DeliveryStatus,
    NotificationDelivery,
)
from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)
from django_notification.outbox import OutboxDeliveryService

pytestmark = pytest.mark.django_db


def test_common_retry_backoff_is_bounded_and_one_based():
    """All three worker paths use the same exponential delay contract."""
    assert [retry_delay_seconds(i, 5, 30) for i in range(1, 6)] == [
        5,
        10,
        20,
        30,
        30,
    ]
    assert retry_delay_seconds(999, 5, 30) == 30


@pytest.mark.parametrize(
    "arguments",
    [
        (0, 60, 5, 3600),
        (101, 60, 5, 3600),
        (5, 4, 5, 3600),
        (5, 3601, 5, 3600),
        (5, 60, 0, 3600),
        (5, 60, 15, 10),
        (5, 60, 5, 86401),
    ],
)
def test_common_retry_configuration_rejects_invalid_limits(arguments):
    """Outbox and provider workers must share the same validation rules."""
    with pytest.raises(ValueError):
        validate_retry_settings(*arguments)


def test_outbox_exhausted_sweep_is_bounded_and_keeps_live_leases():
    """A backlog cannot force a single worker claim to update every row."""
    old = timezone.now() - timedelta(minutes=10)
    rows = [
        NotificationOutboxEvent(
            kind="notification.created",
            payload={},
            attempts=1,
            available_at=old,
        )
        for _ in range(EXHAUSTED_SWEEP_LIMIT + 5)
    ]
    NotificationOutboxEvent.objects.bulk_create(rows, batch_size=250)
    live = NotificationOutboxEvent.objects.create(
        kind="notification.created",
        payload={},
        status=OutboxStatus.PROCESSING,
        attempts=1,
        leased_until=timezone.now() + timedelta(minutes=5),
    )
    worker = OutboxDeliveryService(max_attempts=1)
    assert worker.claim_one() is None
    assert (
        NotificationOutboxEvent.objects.filter(status=OutboxStatus.FAILED).count()
        == EXHAUSTED_SWEEP_LIMIT
    )
    assert (
        NotificationOutboxEvent.objects.filter(status=OutboxStatus.PENDING).count() == 5
    )
    assert worker.claim_one() is None
    assert (
        NotificationOutboxEvent.objects.filter(status=OutboxStatus.FAILED).count()
        == EXHAUSTED_SWEEP_LIMIT + 5
    )
    live.refresh_from_db()
    assert live.status == OutboxStatus.PROCESSING
    assert live.leased_until > timezone.now()


@override_settings(
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS={
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
)
def test_delivery_exhausted_sweep_is_bounded_and_keeps_live_leases(user):
    """Individual provider jobs are reconciled in bounded recovery pages."""
    actor_type = ContentType.objects.get_for_model(user)
    notifications = Notification.objects.bulk_create(
        [
            Notification(
                verb=f"Backlog {i}",
                actor_content_type=actor_type,
                actor_object_id=user.pk,
                category_id="general",
            )
            for i in range(EXHAUSTED_SWEEP_LIMIT + 6)
        ],
        batch_size=250,
    )
    old = timezone.now() - timedelta(minutes=10)
    NotificationDelivery.objects.bulk_create(
        [
            NotificationDelivery(
                notification=notification,
                recipient=user,
                channel="email",
                retry_attempts=1,
                attempts=1,
                available_at=old,
            )
            for notification in notifications[: EXHAUSTED_SWEEP_LIMIT + 5]
        ],
        batch_size=250,
    )
    live = NotificationDelivery.objects.create(
        notification=notifications[-1],
        recipient=user,
        channel="email",
        status=DeliveryStatus.PROCESSING,
        retry_attempts=1,
        attempts=1,
        leased_until=timezone.now() + timedelta(minutes=5),
    )
    worker = NotificationDeliveryService(max_attempts=1)
    assert worker.claim_one() is None
    assert (
        NotificationDelivery.objects.filter(status=DeliveryStatus.FAILED).count()
        == EXHAUSTED_SWEEP_LIMIT
    )
    assert worker.claim_one() is None
    assert (
        NotificationDelivery.objects.filter(status=DeliveryStatus.FAILED).count()
        == EXHAUSTED_SWEEP_LIMIT + 5
    )
    live.refresh_from_db()
    assert live.status == DeliveryStatus.PROCESSING
