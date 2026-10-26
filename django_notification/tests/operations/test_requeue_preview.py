"""Read-only recovery previews preserve worker-owned state."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from django_notification.models import Notification
from django_notification.models.notification_delivery import (
    DeliveryStatus,
    NotificationDelivery,
)
from django_notification.models.notification_digest import NotificationDigest
from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)

pytestmark = pytest.mark.django_db


def test_outbox_requeue_dry_run_does_not_reset_failed_attempts():
    """Operator can preview target IDs without consuming retry history."""
    row = NotificationOutboxEvent.objects.create(
        kind="notification.created",
        payload={},
        status=OutboxStatus.FAILED,
        failed_at=timezone.now(),
        attempts=5,
    )
    output = StringIO()
    call_command(
        "requeue_notification_outbox",
        row.pk,
        "--dry-run",
        stdout=output,
    )
    row.refresh_from_db()
    assert row.status == OutboxStatus.FAILED and row.attempts == 5
    assert "Would requeue 1" in output.getvalue()


def test_delivery_requeue_dry_run_does_not_reset_retry_budget(user):
    """Dry-run matches only FAILED and never touches the job."""
    note = Notification.objects.create_notification(
        actor=user,
        verb="Secret",
        recipients=[user],
        is_sent=True,
    )
    row = NotificationDelivery.objects.create(
        recipient=user,
        notification=note,
        channel="email",
        status=DeliveryStatus.FAILED,
        retry_attempts=4,
    )
    output = StringIO()
    call_command(
        "requeue_notification_deliveries",
        row.pk,
        "--dry-run",
        stdout=output,
    )
    row.refresh_from_db()
    assert row.status == DeliveryStatus.FAILED and row.retry_attempts == 4
    assert "Would requeue 1" in output.getvalue()


def test_digest_requeue_dry_run_does_not_change_children(user):
    """Failed digests and children stay untouched during preview."""
    row = NotificationDigest.objects.create(
        recipient=user,
        channel="email",
        scheduled_at=timezone.now(),
        status=DeliveryStatus.FAILED,
        attempts=3,
    )
    output = StringIO()
    call_command(
        "requeue_notification_digests",
        row.pk,
        "--dry-run",
        stdout=output,
    )
    row.refresh_from_db()
    assert row.status == DeliveryStatus.FAILED and row.attempts == 3
    assert "Would requeue 1" in output.getvalue()
