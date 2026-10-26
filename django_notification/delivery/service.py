"""Durable job fan-out and independent at-least-once channel delivery."""

import logging
import re
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.db import connections, transaction
from django.db.models import F, Q
from django.utils import timezone

from django_notification._worker import (
    fail_exhausted_claims,
    retry_delay_seconds,
    validate_retry_settings,
)
from django_notification.integrations.channels.audience import (
    eligible_audience,
    notification_visible,
)
from django_notification.models.notification_delivery import (
    AttemptStatus,
    DeliveryStatus,
    NotificationDelivery,
    NotificationDeliveryAttempt,
)
from django_notification.models.notification_delivery_schedule import (
    NotificationDeliverySchedule,
)
from django_notification.models.notification_digest import NotificationDigest

from .backends import DeliveryError
from .preferences import blocked_channels_for_users, channel_enabled
from .registry import backend_paths, load_backend
from .routing import routed_channels
from .scheduling import quiet_end_at, schedule_for

logger = logging.getLogger(__name__)
_BATCH_SIZE = 500


# Keep fan-out and child/envelope updates in one explicit transaction.
# pylint: disable-next=too-many-statements
def enqueue_notification_deliveries(notification_id, database="default"):
    """Idempotently persist recipient/channel jobs from a committed event.

    One database transaction rolls back partial fan-out on errors. The unique triple
    prevents duplicated jobs when Phase 13 replays an outbox event. Per-user category
    preferences and dynamic memberships are evaluated at enqueue time, and again
    immediately before invoking a backend.

    """
    if database not in connections:
        raise ValueError("Unknown database alias")
    configured_channels = tuple(backend_paths())
    if not configured_channels:
        return 0
    from django_notification.models.notification import Notification

    notification = (
        Notification.objects.using(database)
        .select_related("category")
        .filter(pk=notification_id)
        .first()
    )
    if notification is None:
        return 0
    channels = routed_channels(notification, configured_channels, database)
    if not channels:
        return 0
    now = timezone.now()
    created_candidates = 0

    # The bounded page joins preferences, schedules and digest identities.
    # pylint: disable-next=too-many-locals
    def write_page(ids):
        """Resolve user scheduling and preference records once per page."""
        nonlocal created_candidates
        blocked = set()
        if not notification.category.is_mandatory:
            blocked = blocked_channels_for_users(
                ids,
                notification.category_id,
                channels,
                database,
            )
        schedules = {
            (item.user_id, item.channel): item
            for item in NotificationDeliverySchedule.objects.using(database).filter(
                user_id__in=ids, channel__in=channels
            )
        }
        batch = []
        digest_cache = {}
        for user_id in ids:
            for channel in channels:
                if (user_id, channel) in blocked:
                    continue
                setting = schedules.get((user_id, channel))
                slot, available = schedule_for(notification, setting, now)
                digest_id = None
                if slot is not None:
                    # The only built-in digest adapter is email. Rejecting
                    # other channels is done at preference validation too.
                    if channel != "email":
                        raise ValueError("Digest scheduling supports email only")
                    key = (user_id, channel, slot)
                    if key not in digest_cache:
                        digest, _ = NotificationDigest.objects.using(
                            database
                        ).get_or_create(
                            recipient_id=user_id,
                            channel=channel,
                            scheduled_at=slot,
                            defaults={"available_at": available},
                        )
                        # Serialize new children with worker finalization so
                        # late fan-out cannot strand a job in a completed slot.
                        digest = (
                            NotificationDigest.objects.using(database)
                            .select_for_update()
                            .get(pk=digest.pk)
                        )
                        digest_cache[key] = digest.pk
                    digest_id = digest_cache[key]
                batch.append(
                    NotificationDelivery(
                        notification_id=notification_id,
                        recipient_id=user_id,
                        channel=channel,
                        digest_id=digest_id,
                        available_at=available,
                    )
                )
        created_candidates += len(batch)
        NotificationDelivery.objects.using(database).bulk_create(
            batch,
            batch_size=_BATCH_SIZE,
            ignore_conflicts=True,
        )

        for digest_id in digest_cache.values():
            envelopes = NotificationDigest.objects.using(database)
            digest = envelopes.get(pk=digest_id)
            pending = NotificationDelivery.objects.using(database).filter(
                digest_id=digest_id,
                status=DeliveryStatus.PENDING,
            )
            if (
                digest.status in (DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED)
                and pending.exists()
            ):
                envelopes.filter(pk=digest_id).update(
                    status=DeliveryStatus.PENDING,
                    attempts=0,
                    available_at=now,
                    delivered_at=None,
                    failed_at=None,
                    lease_token=None,
                    leased_until=None,
                )
            elif digest.status == DeliveryStatus.FAILED:
                # Keep the failed slot's retry policy: late children must
                # participate in the same explicit operator requeue.
                pending.update(status=DeliveryStatus.FAILED, failed_at=digest.failed_at)

    with transaction.atomic(using=database):
        ids = []
        for recipient_id in eligible_audience(notification_id, database):
            ids.append(recipient_id)
            if len(ids) >= _BATCH_SIZE:
                write_page(ids)
                ids.clear()
        if ids:
            write_page(ids)
    # This is the number of eligible candidates, not necessarily newly created
    # rows: conflict-tolerant inserts are intentional.
    return created_candidates


class NotificationDeliveryService:
    """Lease pending jobs, call one backend, record sanitized attempts.

    The worker does not hold a transaction during network I/O. A crashed worker's lease
    is reclaimable; acknowledgements are token-guarded. Thus external sends are at least
    once, never claimed to be exactly once.

    """

    # Preserve the public keyword-only worker configuration API.
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
        self._digest_first = False

    @property
    def rows(self):
        """Route reads and writes consistently through one database alias."""
        return NotificationDelivery.objects.using(self.database)

    @staticmethod
    def _ready(now):
        """Include retry-eligible jobs and abandoned processing leases."""
        return Q(status=DeliveryStatus.PENDING, available_at__lte=now) | Q(
            status=DeliveryStatus.PROCESSING, leased_until__lte=now
        )

    def claim_one(self):
        """Take a finite lease, conditionally, with DB row locks if available."""
        now = timezone.now()
        fail_exhausted_claims(
            self.rows,
            ready=self._ready(now),
            attempt_field="retry_attempts",
            max_attempts=self.max_attempts,
            failed_status=DeliveryStatus.FAILED,
            now=now,
            database=self.database,
        )
        with transaction.atomic(using=self.database):
            query = self.rows.filter(
                self._ready(now),
                retry_attempts__lt=self.max_attempts,
                channel__in=tuple(backend_paths()),
                digest__isnull=True,
            ).order_by("pk")
            features = connections[self.database].features
            if features.has_select_for_update_skip_locked:
                query = query.select_for_update(skip_locked=True)
            elif features.has_select_for_update:
                query = query.select_for_update()
            row = query.first()
            if row is None:
                return None
            token = uuid4()
            changed = (
                self.rows.filter(
                    pk=row.pk,
                    retry_attempts__lt=self.max_attempts,
                )
                .filter(self._ready(now))
                .update(
                    status=DeliveryStatus.PROCESSING,
                    lease_token=token,
                    leased_until=now + timedelta(seconds=self.lease_seconds),
                    attempts=F("attempts") + 1,
                    retry_attempts=F("retry_attempts") + 1,
                )
            )
            if not changed:
                return None
            row.lease_token = token
            row.status = DeliveryStatus.PROCESSING
            row.attempts += 1
            row.retry_attempts += 1
            return row

    def _postpone(self, row, until):
        """Defer a quiet-hours job without consuming a provider attempt."""
        changed = self.rows.filter(
            pk=row.pk,
            status=DeliveryStatus.PROCESSING,
            lease_token=row.lease_token,
        ).update(
            status=DeliveryStatus.PENDING,
            available_at=until,
            lease_token=None,
            leased_until=None,
            attempts=F("attempts") - 1,
            retry_attempts=F("retry_attempts") - 1,
        )
        return "deferred" if changed else "lost_lease"

    def _finish(self, row, status, code):
        """Update only this lease and atomically append one attempt outcome."""
        now = timezone.now()
        retrying = status == AttemptStatus.RETRY
        delay = retry_delay_seconds(
            row.retry_attempts,
            self.retry_base_seconds,
            self.retry_max_seconds,
        )
        if retrying and row.retry_attempts >= self.max_attempts:
            status = AttemptStatus.FAILED
            retrying = False
        terminal = status == AttemptStatus.FAILED
        final_status = (
            DeliveryStatus.PENDING
            if retrying
            else DeliveryStatus.FAILED if terminal else DeliveryStatus.DELIVERED
        )
        with transaction.atomic(using=self.database):
            updated = self.rows.filter(
                pk=row.pk,
                status=DeliveryStatus.PROCESSING,
                lease_token=row.lease_token,
            ).update(
                status=final_status,
                available_at=now + timedelta(seconds=delay) if retrying else now,
                lease_token=None,
                leased_until=None,
                delivered_at=now if status == AttemptStatus.SUCCEEDED else None,
                failed_at=now if terminal else None,
            )
            if not updated:
                return "lost_lease"
            NotificationDeliveryAttempt.objects.using(self.database).create(
                delivery_id=row.pk,
                number=row.attempts,
                status=status,
                code=code,
            )
        return "retry" if retrying else "failed" if terminal else "delivered"

    def _cancel(self, row):
        """Cancel jobs that lost visibility or expired before sending."""
        updated = self.rows.filter(
            pk=row.pk,
            status=DeliveryStatus.PROCESSING,
            lease_token=row.lease_token,
        ).update(
            status=DeliveryStatus.CANCELLED,
            cancelled_at=timezone.now(),
            lease_token=None,
            leased_until=None,
        )
        return "cancelled" if updated else "lost_lease"

    # Each authorization/provider outcome has an explicit guarded transition.
    # pylint: disable-next=too-many-return-statements
    def process_next(self):
        """Alternate due digests and individual jobs to avoid starvation."""
        self._digest_first = not self._digest_first
        if self._digest_first:
            outcome = self.process_next_digest()
            if outcome != "empty":
                return outcome
        row = self.claim_one()
        if row is None:
            return self.process_next_digest() if not self._digest_first else "empty"
        try:
            # Do not send to users that left a dynamic group, opted out,
            # deactivated, deleted the notification, or have expired content.
            _, allowed = notification_visible(
                row.recipient_id, row.notification_id, self.database
            )
            if not allowed:
                return self._cancel(row)
            delivery = self.rows.select_related(
                "recipient", "notification", "notification__category"
            ).get(pk=row.pk)
            if row.channel not in routed_channels(
                delivery.notification,
                backend_paths(),
                self.database,
            ):
                return self._cancel(row)
            if not channel_enabled(
                row.recipient_id,
                delivery.notification.category_id,
                row.channel,
                self.database,
            ):
                return self._cancel(row)
            schedule = (
                NotificationDeliverySchedule.objects.using(self.database)
                .filter(user_id=row.recipient_id, channel=row.channel)
                .first()
            )
            if schedule is not None and not (
                delivery.notification.category.is_mandatory
                or delivery.notification.priority == "URGENT"
            ):
                # Cadence is fixed when enqueued. A later switch to DAILY
                # must not turn a previously immediate job into an orphaned
                # individually-sent "digest"; only quiet hours are live.
                now = timezone.now()
                available = quiet_end_at(now, schedule)
                if available > now:
                    return self._postpone(row, available)
            backend = load_backend(row.channel)
            backend.send(
                delivery,
                idempotency_key=f"djnotify-delivery:{row.pk}",
            )
        except ImproperlyConfigured:
            return self._finish(row, AttemptStatus.FAILED, "backend_config")
        except DeliveryError as exc:
            # Provider subclasses may define their own error code, but only
            # an allowlisted identifier is safe to persist as metadata.
            code = getattr(exc, "code", "delivery_error")
            if not isinstance(code, str) or not re.fullmatch(
                r"[a-z][a-z0-9_]{0,47}", code
            ):
                code = "delivery_error"
            outcome = AttemptStatus.FAILED if exc.permanent else AttemptStatus.RETRY
            return self._finish(row, outcome, code)
        except Exception:  # pylint: disable=broad-exception-caught
            # Never include raw exception text: it can contain API keys,
            # message contents, email addresses, or remote responses.
            logger.warning("Notification external delivery attempt failed")
            return self._finish(row, AttemptStatus.RETRY, "backend_error")
        return self._finish(row, AttemptStatus.SUCCEEDED, "accepted")

    def _digest_ready(self, now):
        """Find due digest envelopes, including expired processing leases."""
        return Q(status=DeliveryStatus.PENDING, available_at__lte=now) | Q(
            status=DeliveryStatus.PROCESSING, leased_until__lte=now
        )

    def _claim_digest(self):
        """Lease one digest envelope; multiple workers never split a batch."""
        now = timezone.now()
        with transaction.atomic(using=self.database):
            envelopes = NotificationDigest.objects.using(self.database)
            exhausted = list(
                envelopes.filter(
                    self._digest_ready(now),
                    attempts__gte=self.max_attempts,
                )
                .order_by("pk")
                .values_list("pk", flat=True)[:_BATCH_SIZE]
            )
            if exhausted:
                envelopes.filter(
                    pk__in=exhausted, attempts__gte=self.max_attempts
                ).filter(
                    self._digest_ready(now),
                ).update(
                    status=DeliveryStatus.FAILED,
                    failed_at=now,
                    lease_token=None,
                    leased_until=None,
                )
                self.rows.filter(
                    digest_id__in=exhausted,
                    digest__status=DeliveryStatus.FAILED,
                    status=DeliveryStatus.PENDING,
                ).update(status=DeliveryStatus.FAILED, failed_at=now)
            query = envelopes.filter(
                self._digest_ready(now),
                attempts__lt=self.max_attempts,
                channel__in=tuple(backend_paths()),
            ).order_by("pk")
            features = connections[self.database].features
            if features.has_select_for_update_skip_locked:
                query = query.select_for_update(skip_locked=True)
            elif features.has_select_for_update:
                query = query.select_for_update()
            batch = query.first()
            if batch is None:
                return None
            token = uuid4()
            updated = (
                NotificationDigest.objects.using(self.database)
                .filter(
                    pk=batch.pk,
                )
                .filter(self._digest_ready(now))
                .update(
                    status=DeliveryStatus.PROCESSING,
                    lease_token=token,
                    leased_until=now + timedelta(seconds=self.lease_seconds),
                    attempts=F("attempts") + 1,
                )
            )
            if not updated:
                return None
            batch.lease_token = token
            batch.attempts += 1
            return batch

    def _finish_digest(self, batch, outcome, jobs=(), force_terminal=False):
        """Record an envelope outcome and child effects in one transaction."""
        now = timezone.now()
        pending = NotificationDelivery.objects.using(self.database)
        digest_rows = NotificationDigest.objects.using(self.database)
        with transaction.atomic(using=self.database):
            locked = (
                digest_rows.select_for_update()
                .filter(
                    pk=batch.pk,
                    status=DeliveryStatus.PROCESSING,
                    lease_token=batch.lease_token,
                )
                .first()
            )
            if locked is None:
                return "lost_lease"
            if outcome == "delivered":
                ids = [job.pk for job in jobs]
                pending.filter(
                    digest_id=batch.pk,
                    pk__in=ids,
                    status=DeliveryStatus.PENDING,
                ).update(
                    status=DeliveryStatus.DELIVERED,
                    delivered_at=now,
                    attempts=F("attempts") + 1,
                )
                for job in jobs:
                    NotificationDeliveryAttempt.objects.using(self.database).create(
                        delivery_id=job.pk,
                        number=job.attempts + 1,
                        status=AttemptStatus.SUCCEEDED,
                        code="digest_accepted",
                    )
                more = pending.filter(
                    digest_id=batch.pk,
                    status=DeliveryStatus.PENDING,
                ).exists()
                digest_rows.filter(pk=batch.pk).update(
                    status=DeliveryStatus.PENDING if more else DeliveryStatus.DELIVERED,
                    available_at=now,
                    delivered_at=None if more else now,
                    lease_token=None,
                    leased_until=None,
                    attempts=0,
                )
                return "delivered"
            if outcome == "deferred":
                return "deferred"  # handled by _postpone_digest
            terminal = force_terminal or batch.attempts >= self.max_attempts
            delay = retry_delay_seconds(
                batch.attempts,
                self.retry_base_seconds,
                self.retry_max_seconds,
            )
            digest_rows.filter(pk=batch.pk).update(
                status=DeliveryStatus.FAILED if terminal else DeliveryStatus.PENDING,
                available_at=now + timedelta(seconds=delay),
                failed_at=now if terminal else None,
                lease_token=None,
                leased_until=None,
            )
            if terminal:
                pending.filter(
                    digest_id=batch.pk,
                    status=DeliveryStatus.PENDING,
                ).update(status=DeliveryStatus.FAILED, failed_at=now)
            return "failed" if terminal else "retry"

    def _postpone_digest(self, batch, until):
        """Quiet hours are not a failed provider attempt."""
        updated = (
            NotificationDigest.objects.using(self.database)
            .filter(
                pk=batch.pk,
                status=DeliveryStatus.PROCESSING,
                lease_token=batch.lease_token,
            )
            .update(
                status=DeliveryStatus.PENDING,
                available_at=until,
                lease_token=None,
                leased_until=None,
                attempts=F("attempts") - 1,
            )
        )
        return "deferred" if updated else "lost_lease"

    # Keep cancellation, deferral and provider outcomes separate.
    # pylint: disable-next=too-many-return-statements
    def process_next_digest(self):
        """Send up to 50 eligible emails in one digest, no content persisted."""
        batch = self._claim_digest()
        if batch is None:
            return "empty"
        try:
            setting = (
                NotificationDeliverySchedule.objects.using(self.database)
                .filter(
                    user_id=batch.recipient_id,
                    channel=batch.channel,
                )
                .first()
            )
            now = timezone.now()
            if setting is not None:
                resumed = quiet_end_at(now, setting)
                if resumed > now:
                    return self._postpone_digest(batch, resumed)
            pending = (
                self.rows.filter(
                    digest_id=batch.pk,
                    status=DeliveryStatus.PENDING,
                )
                .select_related(
                    "recipient",
                    "notification",
                    "notification__category",
                )
                .order_by("pk")
            )
            candidates = list(pending[:50])
            eligible = []
            routes = {}
            for job in candidates:
                route_key = (
                    job.notification.category_id,
                    job.notification.priority,
                    job.notification.status,
                )
                if route_key not in routes:
                    routes[route_key] = routed_channels(
                        job.notification,
                        backend_paths(),
                        self.database,
                    )
                _, allowed = notification_visible(
                    job.recipient_id,
                    job.notification_id,
                    self.database,
                )
                if (
                    allowed
                    and job.channel in routes[route_key]
                    and channel_enabled(
                        job.recipient_id,
                        job.notification.category_id,
                        job.channel,
                        self.database,
                    )
                ):
                    eligible.append(job)
                else:
                    self.rows.filter(
                        pk=job.pk,
                        status=DeliveryStatus.PENDING,
                    ).update(
                        status=DeliveryStatus.CANCELLED,
                        cancelled_at=now,
                    )
            if not eligible:
                if not self.rows.filter(
                    digest_id=batch.pk,
                    status=DeliveryStatus.PENDING,
                ).exists():
                    NotificationDigest.objects.using(self.database).filter(
                        pk=batch.pk,
                        lease_token=batch.lease_token,
                    ).update(
                        status=DeliveryStatus.CANCELLED,
                        lease_token=None,
                        leased_until=None,
                    )
                    return "cancelled"
                return self._finish_digest(batch, "delivered")
            backend = load_backend(batch.channel)
            backend.send_digest(
                batch,
                eligible,
                idempotency_key=f"djnotify-digest:{batch.pk}:{eligible[0].pk}",
            )
            return self._finish_digest(batch, "delivered", eligible)
        except DeliveryError as exc:
            return self._finish_digest(
                batch,
                "failed",
                force_terminal=exc.permanent,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Notification digest delivery failed")
            return self._finish_digest(batch, "failed")

    def process_batch(self, limit=100):
        """Attempt at most ``limit`` jobs, without holding any network locks."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        counts = dict.fromkeys(
            ("delivered", "retry", "failed", "cancelled", "lost_lease", "deferred"), 0
        )
        for _ in range(limit):
            result = self.process_next()
            if result == "empty":
                break
            counts[result] += 1
        return counts
