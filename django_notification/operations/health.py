"""Bounded, privacy-safe metrics for durable notification queues.

A snapshot is a point-in-time observation, not a transactional monitoring lock. No
recipient IDs, event payloads, content or provider error strings are read.

"""

from datetime import datetime

from django.db import connections
from django.db.models import Count, Min, Q
from django.utils import timezone

from django_notification.delivery.registry import CHANNELS
from django_notification.models.notification_delivery import (
    DeliveryStatus,
    NotificationDelivery,
)
from django_notification.models.notification_digest import NotificationDigest
from django_notification.models.notification_outbox_event import NotificationOutboxEvent

QUEUE_STATUSES = (
    "PENDING",
    "PROCESSING",
    "DELIVERED",
    "FAILED",
    "CANCELLED",
)
QUEUE_NAMES = ("outbox", "delivery", "digest")


def _seconds_since(now, point):
    """Return a nonnegative age; zero represents no currently due work."""
    return max(0, int((now - point).total_seconds())) if point else 0


def _aggregate_queue(rows, now):
    """Aggregate queue health with a single conditional SQL query."""
    pending = Q(status="PENDING")
    processing = Q(status="PROCESSING")
    due = pending & Q(available_at__lte=now)
    stale = processing & Q(leased_until__lte=now)
    orphaned = processing & Q(leased_until__isnull=True)
    values = rows.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=pending),
        processing=Count("pk", filter=processing),
        delivered=Count("pk", filter=Q(status="DELIVERED")),
        failed=Count("pk", filter=Q(status="FAILED")),
        cancelled=Count("pk", filter=Q(status="CANCELLED")),
        due_pending=Count("pk", filter=due),
        scheduled=Count("pk", filter=pending & Q(available_at__gt=now)),
        stale_leases=Count("pk", filter=stale),
        stranded_leases=Count("pk", filter=orphaned),
        oldest_due=Min("available_at", filter=due),
        oldest_stale=Min("leased_until", filter=stale),
    )
    times = [
        stamp
        for stamp in (values.pop("oldest_due"), values.pop("oldest_stale"))
        if stamp is not None
    ]
    values["ready"] = values["due_pending"] + values["stale_leases"]
    values["oldest_ready_seconds"] = _seconds_since(now, min(times) if times else None)
    return values


def notification_queue_health(database="default", *, now=None):
    """Return queue counters for one DB alias without accessing private data.

    Delivery counts include *only independent jobs*: pending digest children cannot be
    claimed until the digest envelope is due. Their count is exposed separately to
    prevent false alarms about an immediate-delivery backlog.

    """
    if database not in connections:
        raise ValueError("Unknown database alias")
    captured_at = now or timezone.now()
    if not isinstance(captured_at, datetime) or timezone.is_naive(captured_at):
        raise ValueError("now must be an aware datetime")

    outbox = NotificationOutboxEvent.objects.using(database)
    deliveries = NotificationDelivery.objects.using(database)
    direct = deliveries.filter(digest__isnull=True)
    digests = NotificationDigest.objects.using(database)

    queues = {
        "outbox": _aggregate_queue(outbox, captured_at),
        "delivery": _aggregate_queue(direct, captured_at),
        "digest": _aggregate_queue(digests, captured_at),
    }
    # Only known fixed channel labels appear in exports, regardless of data.
    by_channel: dict[str, dict[str, int]] = {}
    for row in (
        direct.filter(channel__in=CHANNELS)
        .values("channel", "status")
        .annotate(total=Count("pk"))
    ):
        if row["status"] in QUEUE_STATUSES:
            by_channel.setdefault(row["channel"], {})[row["status"]] = row["total"]
    return {
        "captured_at": captured_at.isoformat(),
        "queues": queues,
        "delivery_by_channel": by_channel,
        "digest_child_pending": deliveries.filter(
            digest__isnull=False,
            status=DeliveryStatus.PENDING,
        ).count(),
    }


def evaluate_queue_health(
    snapshot, *, max_ready=1000, max_oldest_seconds=900, max_failed=100, max_stranded=0
):
    """Compare measured counts to explicit, nonnegative operator thresholds."""
    thresholds = (max_ready, max_oldest_seconds, max_failed, max_stranded)
    if any(not isinstance(value, int) or value < 0 for value in thresholds):
        raise ValueError("Queue health thresholds must be nonnegative integers")
    violations = []
    for name in QUEUE_NAMES:
        queue = snapshot["queues"][name]
        checks = (
            ("ready", max_ready),
            ("oldest_ready_seconds", max_oldest_seconds),
            ("failed", max_failed),
            ("stranded_leases", max_stranded),
        )
        for metric, threshold in checks:
            if queue[metric] > threshold:
                violations.append(
                    {
                        "queue": name,
                        "metric": metric,
                        "value": queue[metric],
                        "threshold": threshold,
                    }
                )
    return {"healthy": not violations, "violations": violations}


def prometheus_queue_metrics(snapshot):
    """Emit Prometheus exposition text with fixed, low-cardinality labels."""
    lines = [
        "# HELP django_notification_queue_jobs Durable queue rows by status.",
        "# TYPE django_notification_queue_jobs gauge",
    ]
    for name in QUEUE_NAMES:
        queue = snapshot["queues"][name]
        for status in QUEUE_STATUSES:
            lines.append(
                f'django_notification_queue_jobs{{queue="{name}",status="{status}"}} {queue[status.lower()]}'
            )
    for metric, help_text in (
        ("ready", "Due pending jobs plus expired worker leases."),
        ("scheduled", "Pending jobs scheduled in the future."),
        ("stale_leases", "Processing jobs with expired leases."),
        ("stranded_leases", "Processing jobs lacking a lease deadline."),
        ("oldest_ready_seconds", "Age in seconds of the oldest due job."),
    ):
        name = f"django_notification_queue_{metric}"
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge"))
        for queue_name in QUEUE_NAMES:
            lines.append(
                f'{name}{{queue="{queue_name}"}} '
                f"{snapshot['queues'][queue_name][metric]}"
            )
    lines.extend(
        (
            "# HELP django_notification_delivery_channel_jobs Jobs by configured channel and status.",
            "# TYPE django_notification_delivery_channel_jobs gauge",
        )
    )
    for channel in sorted(snapshot["delivery_by_channel"]):
        for status in QUEUE_STATUSES:
            count = snapshot["delivery_by_channel"][channel].get(status, 0)
            lines.append(
                f'django_notification_delivery_channel_jobs{{channel="{channel}",status="{status}"}} {count}'
            )
    lines.extend(
        (
            "# HELP django_notification_digest_child_pending Pending digest child jobs.",
            "# TYPE django_notification_digest_child_pending gauge",
            f"django_notification_digest_child_pending {snapshot['digest_child_pending']}",
        )
    )
    return "\n".join(lines) + "\n"
