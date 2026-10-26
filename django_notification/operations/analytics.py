"""Privacy-safe historical analytics for external notification delivery.

Reports describe a cohort of *jobs created in the window*, observed as of the report
cutoff. Metrics exclude pruned jobs and never inspect user identities, notification
content, rendered messages, or provider error strings.

"""

import re
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone

from django.db import connections
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from django_notification.delivery.registry import CHANNELS
from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.models.notification_delivery import (
    AttemptStatus,
    DeliveryStatus,
    NotificationDelivery,
    NotificationDeliveryAttempt,
)

_STATUSES = tuple(status.value for status in DeliveryStatus)
_PRIORITIES = tuple(priority.value for priority in NotificationPriority)
_SAFE_CATEGORY = re.compile(r"[a-zA-Z0-9_-]{1,64}\Z")
_LATENCY_BUCKETS = (
    ("under_5s", timedelta(0), timedelta(seconds=5)),
    ("5_to_30s", timedelta(seconds=5), timedelta(seconds=30)),
    ("30s_to_5m", timedelta(seconds=30), timedelta(minutes=5)),
    ("5m_to_1h", timedelta(minutes=5), timedelta(hours=1)),
    ("1h_or_more", timedelta(hours=1), None),
)


def _latency_queryset(rows):
    """Annotate DB-side queue-to-ack latency without loading individual jobs."""
    return rows.annotate(
        _queue_latency=ExpressionWrapper(
            F("delivered_at") - F("created_at"),
            output_field=DurationField(),
        ),
    )


def _stat_expressions():
    """Build stable status counters shared by totals and grouped reports."""
    valid_latency = Q(
        status=DeliveryStatus.DELIVERED,
        delivered_at__isnull=False,
        _queue_latency__gte=timedelta(0),
    )
    expressions = {
        "total": Count("pk"),
        "average_latency": Avg("_queue_latency", filter=valid_latency),
        "maximum_latency": Max("_queue_latency", filter=valid_latency),
        "retried_jobs": Count("pk", filter=Q(attempts__gte=2)),
    }
    for status in _STATUSES:
        expressions[status.lower()] = Count(
            "pk",
            filter=Q(status=status),
        )
    return expressions


def _seconds(value):
    """Convert an aggregated duration to stable seconds or unavailable."""
    return round(max(0.0, value.total_seconds()), 3) if value is not None else None


def _normalize_stat(row):
    """Convert SQL aggregates to JSON-safe totals and explicit denominators."""
    result = {
        "total": row["total"],
        "pending": row["pending"],
        "processing": row["processing"],
        "delivered": row["delivered"],
        "failed": row["failed"],
        "cancelled": row["cancelled"],
        "retried_jobs": row["retried_jobs"],
    }
    terminal = result["delivered"] + result["failed"]
    result["terminal_jobs"] = terminal
    result["terminal_success_rate_percent"] = (
        round(100 * result["delivered"] / terminal, 2) if terminal else None
    )
    result["average_queue_latency_seconds"] = _seconds(row["average_latency"])
    result["maximum_queue_latency_seconds"] = _seconds(row["maximum_latency"])
    return result


def _stats(rows):
    """Aggregate one dataset without materializing any delivery jobs."""
    return _normalize_stat(
        _latency_queryset(rows).aggregate(
            **_stat_expressions(),
        )
    )


def _group_stats(rows, path, allowed):
    """Return fixed-dimension groups, combining unexpected labels as other."""
    aggregates = _stat_expressions()
    found = {
        row[path]: _normalize_stat(row)
        for row in _latency_queryset(
            rows.filter(
                **{f"{path}__in": allowed},
            )
        )
        .values(path)
        .annotate(**aggregates)
        .order_by(path)
    }
    result = [{"key": key, **found.get(key, _zero_stats())} for key in allowed]
    other = _stats(rows.exclude(**{f"{path}__in": allowed}))
    if other["total"]:
        result.append({"key": "other", **other})
    return result


def _zero_stats():
    """Represent an empty group without claiming a zero-percent success rate."""
    return _normalize_stat(
        {
            "total": 0,
            "average_latency": None,
            "maximum_latency": None,
            "retried_jobs": 0,
            **{status.lower(): 0 for status in _STATUSES},
        }
    )


def _categories(rows, limit):
    """Aggregate top categories and roll remaining/invalid ones into other."""
    records = list(
        _latency_queryset(rows)
        .values("notification__category_id")
        .annotate(**_stat_expressions())
        .order_by("-total", "notification__category_id")[:limit]
    )
    selected = [
        row
        for row in records
        if _SAFE_CATEGORY.fullmatch(row["notification__category_id"] or "")
    ]
    output = [
        {"key": row["notification__category_id"], **_normalize_stat(row)}
        for row in selected
    ]
    remaining = _stats(
        rows.exclude(
            notification__category_id__in=[
                row["notification__category_id"] for row in selected
            ],
        )
    )
    if remaining["total"]:
        output.append({"key": "other", **remaining})
    return output


def _retry_claim_distribution(rows):
    """Job claim counts, not provider-attempt counts or per-user records."""
    values = rows.aggregate(
        none=Count("pk", filter=Q(attempts=0)),
        once=Count("pk", filter=Q(attempts=1)),
        twice=Count("pk", filter=Q(attempts=2)),
        three_to_four=Count(
            "pk",
            filter=Q(
                attempts__gte=3,
                attempts__lte=4,
            ),
        ),
        five_plus=Count("pk", filter=Q(attempts__gte=5)),
    )
    return values


def _latency_distribution(rows):
    """Calculate mutually exclusive nonnegative delivery-latency buckets."""
    expressions = {}
    for label, lower, upper in _LATENCY_BUCKETS:
        condition = Q(
            status=DeliveryStatus.DELIVERED,
            delivered_at__isnull=False,
            _queue_latency__gte=lower,
        )
        if upper is not None:
            condition &= Q(_queue_latency__lt=upper)
        expressions[label] = Count("pk", filter=condition)
    return _latency_queryset(rows).aggregate(**expressions)


def _daily_cohorts(rows, start, end):
    """Use fixed UTC dates, including empty days, with bounded row counts."""
    observed = {
        entry["day"]: entry
        for entry in rows.annotate(
            day=TruncDate(
                "created_at",
                tzinfo=datetime_timezone.utc,
            )
        )
        .values("day")
        .annotate(
            total=Count("pk"),
            delivered=Count("pk", filter=Q(status=DeliveryStatus.DELIVERED)),
            failed=Count("pk", filter=Q(status=DeliveryStatus.FAILED)),
        )
    }
    day = start.date()
    last = end.date()
    data = []
    while day <= last:
        entry = observed.get(day, {})
        data.append(
            {
                "day": day.isoformat(),
                "total": entry.get("total", 0),
                "delivered": entry.get("delivered", 0),
                "failed": entry.get("failed", 0),
            }
        )
        day += timedelta(days=1)
    return data


def notification_delivery_analytics(
    database="default", *, days=30, category_limit=10, now=None
):
    """Return aggregate, read-only job-cohort analytics from one DB alias.

    The UTC cohort window is [now - days, now). Current job status is sampled
    when queries run. Attempts are restricted to that cohort and the cutoff.
    Success rates exclude queued/cancelled jobs; no completed jobs => null.
    The report excludes old records removed by cleanup and includes no
    recipient or notification IDs, body text, rendered templates or raw codes.

    """
    if database not in connections:
        raise ValueError("Unknown database alias")
    # Exact int check deliberately rejects bool values.
    if (
        type(days) is not int  # pylint: disable=unidiomatic-typecheck
        or not 1 <= days <= 365
    ):
        raise ValueError("days must be between 1 and 365")
    # Exact int check deliberately rejects bool values.
    if (
        type(category_limit) is not int  # pylint: disable=unidiomatic-typecheck
        or not 1 <= category_limit <= 50
    ):
        raise ValueError("category_limit must be between 1 and 50")
    end = timezone.now() if now is None else now
    if not isinstance(end, datetime) or timezone.is_naive(end):
        raise ValueError("now must be an aware datetime")
    end = end.astimezone(datetime_timezone.utc)
    start = end - timedelta(days=days)
    rows = NotificationDelivery.objects.using(database).filter(
        created_at__gte=start,
        created_at__lt=end,
    )
    attempts = NotificationDeliveryAttempt.objects.using(database).filter(
        delivery__created_at__gte=start,
        delivery__created_at__lt=end,
        completed_at__lt=end,
    )
    attempt_counts = attempts.aggregate(
        total=Count("pk"),
        succeeded=Count("pk", filter=Q(status=AttemptStatus.SUCCEEDED)),
        retry=Count("pk", filter=Q(status=AttemptStatus.RETRY)),
        failed=Count("pk", filter=Q(status=AttemptStatus.FAILED)),
    )
    return {
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days,
            "timezone": "UTC",
            "cohort_field": "created_at",
        },
        "overall": _stats(rows),
        "by_channel": _group_stats(rows, "channel", sorted(CHANNELS)),
        "by_priority": _group_stats(
            rows,
            "notification__priority",
            _PRIORITIES,
        ),
        "by_category": _categories(rows, category_limit),
        "attempt_outcomes": attempt_counts,
        "job_claim_distribution": _retry_claim_distribution(rows),
        "queue_latency_distribution": _latency_distribution(rows),
        "daily_cohorts": _daily_cohorts(rows, start, end),
    }
