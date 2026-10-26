"""Sanitized operator diagnostics for failed notification delivery queues."""

import re
from datetime import timedelta
from typing import Any

from django.db import connections
from django.db.models import Count
from django.utils import timezone

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

_SAFE_CODE = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")


def notification_failure_report(
    database="default", *, since_hours=24, show_ids=False, limit=20, now=None
):
    """Report failures without fetching payloads, contacts or message bodies.

    The report is bounded to 20 different sanitized attempt codes and, when explicitly
    requested, at most 100 row identifiers per queue. IDs are internal job/event
    identities only, not user or notification identities.

    """
    if database not in connections:
        raise ValueError("Unknown database alias")
    if not isinstance(since_hours, int) or not 1 <= since_hours <= 8760:
        raise ValueError("since_hours must be between 1 and 8760")
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    moment = now or timezone.now()
    boundary = moment - timedelta(hours=since_hours)
    sources = {
        "outbox": NotificationOutboxEvent.objects.using(database).filter(
            status=OutboxStatus.FAILED,
            failed_at__gte=boundary,
        ),
        "delivery": NotificationDelivery.objects.using(database).filter(
            status=DeliveryStatus.FAILED,
            failed_at__gte=boundary,
        ),
        "digest": NotificationDigest.objects.using(database).filter(
            status=DeliveryStatus.FAILED,
            failed_at__gte=boundary,
        ),
    }
    result: dict[str, Any] = {"since_hours": since_hours, "terminal_failures": {}}
    for name, qs in sources.items():
        part: dict[str, Any] = {"count": qs.count()}
        if show_ids:
            part["job_ids"] = list(
                qs.order_by("-failed_at", "-pk").values_list("pk", flat=True)[:limit]
            )
        result["terminal_failures"][name] = part

    # Only fixed, sanitized code tokens; never read exception messages.
    attempts = NotificationDeliveryAttempt.objects.using(database).filter(
        completed_at__gte=boundary,
        status__in=(AttemptStatus.RETRY, AttemptStatus.FAILED),
    )
    raw = list(
        attempts.values("code")
        .annotate(total=Count("pk"))
        .order_by("-total", "code")[:20]
    )
    result["attempt_codes"] = [
        {
            "code": (
                row["code"]
                if _SAFE_CODE.fullmatch(row["code"] or "")
                else "invalid_code"
            ),
            "count": row["total"],
        }
        for row in raw
    ]
    return result
