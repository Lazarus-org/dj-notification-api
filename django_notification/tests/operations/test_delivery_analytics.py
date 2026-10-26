"""Phase 19: cohort semantics, bounded groupings, latency and privacy."""

import csv
import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from django_notification.models import Notification, NotificationCategory
from django_notification.models.notification_delivery import (
    AttemptStatus,
    DeliveryStatus,
    NotificationDelivery,
    NotificationDeliveryAttempt,
)
from django_notification.operations.analytics import notification_delivery_analytics


pytestmark = pytest.mark.django_db


def _job(
    user,
    created,
    *,
    status=DeliveryStatus.PENDING,
    channel="email",
    category="general",
    priority="NORMAL",
    attempts=0,
    delivered_at=None,
):
    """Build one job; override auto_now_add for a deterministic cohort."""
    notification = Notification.objects.create_notification(
        actor=user,
        verb="Sensitive subject",
        description="Private content",
        recipients=[user],
        is_sent=True,
        category=category,
        priority=priority,
    )
    job = NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel=channel,
        status=status,
        attempts=attempts,
        delivered_at=delivered_at,
    )
    NotificationDelivery.objects.filter(pk=job.pk).update(created_at=created)
    job.refresh_from_db()
    return job


def test_terminal_success_rate_excludes_pending_and_cancelled_jobs(user):
    """A one-success/one-failure completed cohort is 50%, not 25%."""
    now = timezone.now()
    for status in (
        DeliveryStatus.DELIVERED,
        DeliveryStatus.FAILED,
        DeliveryStatus.PENDING,
        DeliveryStatus.CANCELLED,
    ):
        _job(user, now - timedelta(hours=1), status=status)
    result = notification_delivery_analytics(days=2, now=now)
    overall = result["overall"]
    assert overall["total"] == 4
    assert overall["terminal_jobs"] == 2
    assert overall["terminal_success_rate_percent"] == 50.0
    assert overall["pending"] == 1
    assert overall["cancelled"] == 1
    assert sum(row["total"] for row in result["by_category"]) == 4
    assert sum(row["total"] for row in result["by_channel"]) == 4


def test_cohort_window_is_half_open_and_empty_rates_are_null(user):
    """Exclude older and later-created jobs, rather than filtering by ack."""
    now = timezone.now()
    _job(user, now - timedelta(days=3), status=DeliveryStatus.DELIVERED)
    _job(user, now, status=DeliveryStatus.DELIVERED)
    _job(user, now - timedelta(hours=1))
    result = notification_delivery_analytics(days=2, now=now)
    assert result["overall"]["total"] == 1
    assert result["overall"]["terminal_success_rate_percent"] is None
    assert result["overall"]["average_queue_latency_seconds"] is None
    assert sum(item["total"] for item in result["daily_cohorts"]) == 1


def test_latency_buckets_and_average_are_queue_to_ack_times(user):
    """Report completion latency, not provider network latency."""
    now = timezone.now()
    _job(
        user,
        now - timedelta(seconds=20),
        status=DeliveryStatus.DELIVERED,
        delivered_at=now - timedelta(seconds=10),
    )
    _job(
        user,
        now - timedelta(seconds=90),
        status=DeliveryStatus.DELIVERED,
        delivered_at=now - timedelta(seconds=30),
    )
    result = notification_delivery_analytics(days=2, now=now)
    stats = result["overall"]
    assert stats["average_queue_latency_seconds"] == 35.0
    assert stats["maximum_queue_latency_seconds"] == 60.0
    assert result["queue_latency_distribution"]["5_to_30s"] == 1
    assert result["queue_latency_distribution"]["30s_to_5m"] == 1
    assert sum(result["queue_latency_distribution"].values()) == 2


def test_attempt_outcomes_and_claim_distribution_are_distinct(user):
    """Retry claims can exceed persisted external-provider outcomes."""
    now = timezone.now()
    job = _job(
        user,
        now - timedelta(hours=2),
        status=DeliveryStatus.DELIVERED,
        attempts=2,
        delivered_at=now - timedelta(hours=1),
    )
    NotificationDeliveryAttempt.objects.create(
        delivery=job,
        number=1,
        status=AttemptStatus.RETRY,
        code="retry_safe",
        completed_at=now - timedelta(hours=1),
    )
    NotificationDeliveryAttempt.objects.create(
        delivery=job,
        number=2,
        status=AttemptStatus.SUCCEEDED,
        code="accepted",
        completed_at=now - timedelta(minutes=1),
    )
    result = notification_delivery_analytics(now=now)
    assert result["overall"]["retried_jobs"] == 1
    assert result["attempt_outcomes"] == {
        "total": 2,
        "succeeded": 1,
        "retry": 1,
        "failed": 0,
    }
    assert result["job_claim_distribution"]["twice"] == 1
    assert "retry_safe" not in json.dumps(result)
    assert "Sensitive subject" not in json.dumps(result)
    assert "Private content" not in json.dumps(result)


def test_category_cap_rolls_other_categories_up_without_losing_totals(user):
    """A bounded category list aggregates the rest into a single other row."""
    now = timezone.now()
    for slug in ("one", "two", "three"):
        NotificationCategory.objects.create(slug=slug, name=slug)
        _job(user, now - timedelta(hours=1), category=slug)
    result = notification_delivery_analytics(
        days=2,
        now=now,
        category_limit=1,
    )
    assert len(result["by_category"]) == 2
    assert result["by_category"][-1]["key"] == "other"
    assert result["by_category"][-1]["total"] == 2
    assert sum(row["total"] for row in result["by_category"]) == 3


def test_invalid_channel_and_priority_never_appear_as_labels(user):
    """Unexpected database values go into fixed 'other' buckets."""
    now = timezone.now()
    job = _job(
        user,
        now - timedelta(hours=1),
        channel="PRIVATE_CHANNEL",
    )
    # Bypass application validation to model a legacy/corrupt database value.
    Notification.objects.filter(pk=job.notification_id).update(
        priority="SECRET",
    )
    result = notification_delivery_analytics(now=now)
    assert {entry["key"]: entry["total"] for entry in result["by_channel"]}[
        "other"
    ] == 1
    assert {entry["key"]: entry["total"] for entry in result["by_priority"]}[
        "other"
    ] == 1
    assert "PRIVATE_CHANNEL" not in json.dumps(result)
    assert "SECRET" not in json.dumps(result)


def test_command_json_and_csv_have_no_personal_identifiers(user):
    """Machine-readable exports are aggregated and need no API endpoint."""
    now = timezone.now()
    _job(user, now - timedelta(hours=1), status=DeliveryStatus.FAILED)
    output = StringIO()
    call_command("notification_delivery_report", "--json", stdout=output)
    result = json.loads(output.getvalue())
    assert result["overall"]["failed"] == 1
    assert "Sensitive subject" not in output.getvalue()
    assert str(user.email) not in output.getvalue()
    table = StringIO()
    call_command("notification_delivery_report", "--csv", stdout=table)
    rows = list(csv.DictReader(StringIO(table.getvalue())))
    assert rows[0]["dimension"] == "overall"
    assert rows[0]["failed"] == "1"
    assert "Private content" not in table.getvalue()


def test_validation_rejects_invalid_ranges_or_database():
    """Bounded reports reject untrusted command options before querying."""
    with pytest.raises(ValueError):
        notification_delivery_analytics(days=0)
    with pytest.raises(ValueError):
        notification_delivery_analytics(days=366)
    with pytest.raises(ValueError):
        notification_delivery_analytics(category_limit=0)
    with pytest.raises(ValueError):
        notification_delivery_analytics(database="missing")
    with pytest.raises(ValueError):
        notification_delivery_analytics(now=timezone.now().replace(tzinfo=None))
    with pytest.raises(CommandError):
        call_command("notification_delivery_report", "--days=0")
