"""Optional database-backed delivery of notification lifecycle events.

The outbox is *at least once*: a worker may crash after invoking a receiver but before
recording success. Receivers must tolerate repeated event IDs.

"""

import logging
from dataclasses import asdict
from datetime import timedelta
from uuid import uuid4

from django.db import connections, transaction
from django.db.models import F, Q
from django.utils import timezone

from django_notification._worker import (
    fail_exhausted_claims,
    retry_delay_seconds,
    validate_retry_settings,
)
from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)

logger = logging.getLogger(__name__)


class NoEventReceivers(RuntimeError):
    """Refuse to acknowledge an event if no receiver is registered."""


class OutboxDeliveryService:
    """Claim, deliver and acknowledge events on a specified database alias.

    One short transaction acquires a lease. Receiver callbacks execute outside that
    transaction. A token-guarded acknowledgement prevents a stale worker from
    overwriting the result of a newer claim after lease expiry.

    """

    # Preserve the public keyword-only lease and retry configuration API.
    # pylint: disable-next=too-many-arguments
    def __init__(
        self,
        database="default",
        *,
        max_attempts=5,
        lease_seconds=60,
        retry_base_seconds=5,
        retry_max_seconds=3600,
    ):
        if database not in connections:
            raise ValueError("Unknown database alias")
        validate_retry_settings(
            max_attempts,
            lease_seconds,
            retry_base_seconds,
            retry_max_seconds,
        )
        self.database = database
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    @property
    def rows(self):
        """Use the selected alias for every read and write."""
        return NotificationOutboxEvent.objects.using(self.database)

    @staticmethod
    def _ready(now):
        """Include abandoned claims whose lease expired."""
        return Q(status=OutboxStatus.PENDING, available_at__lte=now) | Q(
            status=OutboxStatus.PROCESSING, leased_until__lte=now
        )

    def claim_one(self):
        """Atomically claim the next available row, or return ``None``."""
        now = timezone.now()
        token = uuid4()
        # Reconcile one bounded page of exhausted leases. Never lock the whole
        # expired backlog at once, even if a worker was offline for days.
        fail_exhausted_claims(
            self.rows,
            ready=self._ready(now),
            attempt_field="attempts",
            max_attempts=self.max_attempts,
            failed_status=OutboxStatus.FAILED,
            now=now,
            database=self.database,
        )
        with transaction.atomic(using=self.database):
            qs = self.rows.filter(
                self._ready(now), attempts__lt=self.max_attempts
            ).order_by("pk")
            if connections[self.database].features.has_select_for_update_skip_locked:
                qs = qs.select_for_update(skip_locked=True)
            elif connections[self.database].features.has_select_for_update:
                qs = qs.select_for_update()
            candidate = qs.first()
            if candidate is None:
                return None
            updated = (
                self.rows.filter(pk=candidate.pk, attempts__lt=self.max_attempts)
                .filter(self._ready(now))
                .update(
                    status=OutboxStatus.PROCESSING,
                    lease_token=token,
                    leased_until=now + timedelta(seconds=self.lease_seconds),
                    attempts=F("attempts") + 1,
                )
            )
            if not updated:
                return None
            candidate.status = OutboxStatus.PROCESSING
            candidate.lease_token = token
            candidate.attempts += 1
            return candidate

    def _acknowledge(self, row):
        """Only the current lease holder can mark delivery successful."""
        changed = self.rows.filter(
            pk=row.pk,
            status=OutboxStatus.PROCESSING,
            lease_token=row.lease_token,
        ).update(
            status=OutboxStatus.DELIVERED,
            delivered_at=timezone.now(),
            lease_token=None,
            leased_until=None,
        )
        return bool(changed)

    def _retry(self, row):
        """Schedule a bounded exponential retry or a terminal failed state."""
        now = timezone.now()
        exhausted = row.attempts >= self.max_attempts
        delay = retry_delay_seconds(
            row.attempts,
            self.retry_base_seconds,
            self.retry_max_seconds,
        )
        changed = self.rows.filter(
            pk=row.pk,
            status=OutboxStatus.PROCESSING,
            lease_token=row.lease_token,
        ).update(
            status=(OutboxStatus.FAILED if exhausted else OutboxStatus.PENDING),
            available_at=now + timedelta(seconds=delay),
            failed_at=now if exhausted else None,
            lease_token=None,
            leased_until=None,
        )
        return ("failed" if exhausted else "retry") if changed else "lost_lease"

    def process_next(self):
        """Deliver one event with retry handling; return a status string."""
        from django_notification.events import NotificationEvent, notification_event
        from django_notification.models.notification import Notification

        row = self.claim_one()
        if row is None:
            return "empty"
        try:
            if not notification_event.has_listeners(sender=Notification):
                raise NoEventReceivers("No notification event receivers registered")
            payload = dict(row.payload)
            payload["fields"] = tuple(payload.get("fields") or ())
            event = NotificationEvent(**payload)
            # All receivers must succeed before acknowledging. If one fails,
            # other receivers may have run and must be idempotent on replay.
            notification_event.send(
                sender=Notification,
                event=event,
                outbox_event_id=row.pk,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Never store exception messages or notification/user content.
            logger.warning("Notification outbox delivery attempt failed")
            return self._retry(row)
        return "delivered" if self._acknowledge(row) else "lost_lease"

    def process_batch(self, limit=100):
        """Run a bounded batch without an open transaction around receivers."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        counts = {"delivered": 0, "retry": 0, "failed": 0, "lost_lease": 0}
        for _ in range(limit):
            result = self.process_next()
            if result == "empty":
                break
            counts[result] += 1
        return counts


def enqueue_event(event):
    """Insert a durable event within its source mutation transaction."""
    if not connections[event.database].in_atomic_block:
        raise RuntimeError("Outbox publishing requires an active transaction")
    return NotificationOutboxEvent.objects.using(event.database).create(
        kind=event.kind,
        payload=asdict(event),
    )
