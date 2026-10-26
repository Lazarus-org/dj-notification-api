"""Queue observability covers state, timing, privacy and operator limits."""

import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from django_notification.models import Notification
from django_notification.models.notification_delivery import (
    AttemptStatus,
    DeliveryStatus,
    NotificationDelivery,
    NotificationDeliveryAttempt,
)
from django_notification.models.notification_digest import NotificationDigest
from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)
from django_notification.operations.failures import notification_failure_report
from django_notification.operations.health import (
    evaluate_queue_health,
    notification_queue_health,
    prometheus_queue_metrics,
)

pytestmark = pytest.mark.django_db


def _create_notification(user):
    return Notification.objects.create_notification(
        actor=user,
        verb="Private message",
        recipients=[user],
        is_sent=True,
    )


def test_health_distinguishes_due_future_and_expired_leases(user):
    """Only actionable jobs count as ready, not scheduled digest children."""
    now = timezone.now()
    notification = _create_notification(user)
    digest = NotificationDigest.objects.create(
        recipient=user,
        channel="email",
        scheduled_at=now + timedelta(days=1),
        available_at=now + timedelta(days=1),
    )
    NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel="email",
        digest=digest,
        available_at=now - timedelta(hours=2),
    )
    NotificationOutboxEvent.objects.create(
        kind="notification.created",
        payload={},
        available_at=now - timedelta(seconds=30),
    )
    NotificationOutboxEvent.objects.create(
        kind="notification.sent",
        payload={},
        available_at=now + timedelta(minutes=10),
    )
    NotificationOutboxEvent.objects.create(
        kind="notification.updated",
        payload={},
        status=OutboxStatus.PROCESSING,
        leased_until=now - timedelta(seconds=40),
    )
    report = notification_queue_health(now=now)
    assert report["queues"]["outbox"]["ready"] == 2
    assert report["queues"]["outbox"]["scheduled"] == 1
    assert report["queues"]["outbox"]["stale_leases"] == 1
    assert report["queues"]["outbox"]["oldest_ready_seconds"] >= 39
    assert report["queues"]["delivery"]["ready"] == 0
    assert report["queues"]["digest"]["scheduled"] == 1
    assert report["digest_child_pending"] == 1


def test_health_reports_stranded_processing_and_channel_aggregates(user):
    """Missing lease deadline is an alert, not a runnable claim."""
    now = timezone.now()
    notification = _create_notification(user)
    NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel="email",
        status=DeliveryStatus.PROCESSING,
        leased_until=None,
    )
    report = notification_queue_health(now=now)
    assert report["queues"]["delivery"]["stranded_leases"] == 1
    assert report["queues"]["delivery"]["ready"] == 0
    assert report["delivery_by_channel"]["email"]["PROCESSING"] == 1
    verdict = evaluate_queue_health(report)
    assert not verdict["healthy"]
    assert verdict["violations"][0]["metric"] == "stranded_leases"
    assert "recipient" not in prometheus_queue_metrics(report)
    assert "Private message" not in prometheus_queue_metrics(report)


def test_health_command_json_prometheus_and_exit_code():
    """Monitoring output supports machine parsing and threshold failures."""
    NotificationOutboxEvent.objects.create(
        kind="notification.created",
        payload={},
    )
    result = StringIO()
    call_command("notification_queue_health", "--json", stdout=result)
    payload = json.loads(result.getvalue())
    assert payload["queues"]["outbox"]["ready"] == 1
    assert payload["healthy"]
    metric = StringIO()
    call_command("notification_queue_health", "--prometheus", stdout=metric)
    assert 'django_notification_queue_ready{queue="outbox"} 1' in metric.getvalue()
    with pytest.raises(CommandError):
        call_command(
            "notification_queue_health",
            "--max-ready=0",
            "--fail-on-unhealthy",
            stdout=StringIO(),
        )
    with pytest.raises(CommandError):
        call_command("notification_queue_health", "--max-ready=-1")


def test_failure_report_is_redacted_and_bounded(user):
    """Provider messages, users and notification content never surface."""
    now = timezone.now()
    notification = _create_notification(user)
    job = NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel="email",
        status=DeliveryStatus.FAILED,
        failed_at=now,
    )
    NotificationDeliveryAttempt.objects.create(
        delivery=job,
        number=1,
        status=AttemptStatus.FAILED,
        code="provider_error",
        completed_at=now,
    )
    report = notification_failure_report(now=now)
    assert report["terminal_failures"]["delivery"] == {"count": 1}
    assert report["attempt_codes"] == [
        {
            "code": "provider_error",
            "count": 1,
        }
    ]
    assert "Private message" not in json.dumps(report)
    assert "job_ids" not in json.dumps(report)
    ids = notification_failure_report(now=now, show_ids=True, limit=1)
    assert ids["terminal_failures"]["delivery"]["job_ids"] == [job.pk]
    with pytest.raises(ValueError):
        notification_failure_report(limit=101)


def test_failure_report_excludes_old_history_and_scrubs_invalid_codes(user):
    """Historical failures age out of the window; labels stay controlled."""
    now = timezone.now()
    notification = _create_notification(user)
    job = NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel="email",
        status=DeliveryStatus.FAILED,
        failed_at=now - timedelta(hours=30),
    )
    NotificationDeliveryAttempt.objects.create(
        delivery=job,
        number=1,
        status=AttemptStatus.FAILED,
        code="not safe: customer@example.com",
        completed_at=now,
    )
    report = notification_failure_report(now=now)
    assert report["terminal_failures"]["delivery"]["count"] == 0
    assert report["attempt_codes"] == [{"code": "invalid_code", "count": 1}]
    buffer = StringIO()
    call_command("notification_failure_report", "--json", stdout=buffer)
    assert "customer@example.com" not in buffer.getvalue()
    assert "invalid_code" in buffer.getvalue()
