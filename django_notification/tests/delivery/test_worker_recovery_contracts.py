"""Fault injection around durable claims and provider recovery boundaries."""

from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.db import connection
from django.db.models import QuerySet
from django.test import override_settings
from django.utils import timezone

from django_notification.delivery import service as workers
from django_notification.delivery.backends import DeliveryError, PermanentDeliveryError
from django_notification.events import NotificationEvent
from django_notification.models import NotificationDelivery, NotificationDigest
from django_notification.models.notification_routing_rule import NotificationRoutingRule
from django_notification.outbox import OutboxDeliveryService, enqueue_event
from django_notification.tests.delivery.test_schedules_digests import (
    _created,
    _schedule,
)
from django_notification.tests.delivery.test_templates_preferences import _delivery

BACKENDS = {"email": "django_notification.delivery.backends.DjangoEmailBackend"}
pytestmark = pytest.mark.django_db


def _digest(user, attempts=0):
    now = timezone.now()
    digest = NotificationDigest.objects.create(
        recipient=user,
        channel="email",
        scheduled_at=now,
        available_at=now,
        attempts=attempts,
    )
    job = _delivery(user)
    job.digest = digest
    job.save(update_fields=["digest"])
    return digest, job


def test_fanout_rejects_unknown_database_and_handles_no_work(user):
    with pytest.raises(ValueError, match="database"):
        workers.enqueue_notification_deliveries(1, "missing")
    assert workers.enqueue_notification_deliveries(1) == 0
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS):
        assert workers.enqueue_notification_deliveries(999999) == 0
        item = _created(user)
        NotificationRoutingRule.objects.create(
            name="No external delivery", action="REMOVE", channels=["email"]
        )
        assert workers.enqueue_notification_deliveries(item.pk) == 0


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_fanout_flushes_full_and_partial_pages(user, another_user):
    item = _created(user)
    item.recipient.add(another_user)
    with patch.object(workers, "_BATCH_SIZE", 1):
        assert workers.enqueue_notification_deliveries(item.pk) == 2
    assert NotificationDelivery.objects.filter(notification=item).count() == 2


def test_corrupt_non_email_digest_schedule_rolls_back_fanout(user):
    with override_settings(
        DJANGO_NOTIFICATION_DELIVERY_BACKENDS={"sms": BACKENDS["email"]}
    ):
        from django_notification.models import NotificationDeliverySchedule

        NotificationDeliverySchedule.objects.create(
            user=user, channel="sms", frequency="DAILY"
        )
        with pytest.raises(ValueError, match="email only"):
            workers.enqueue_notification_deliveries(_created(user).pk)
    assert not NotificationDelivery.objects.exists()
    assert not NotificationDigest.objects.exists()


@pytest.mark.parametrize("kind", ["direct", "digest", "outbox"])
@pytest.mark.parametrize("skip_locked", [True, False])
@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_claim_selects_supported_locking_strategy(user, kind, skip_locked):
    if kind == "direct":
        _delivery(user)
        claim = workers.NotificationDeliveryService().claim_one
    elif kind == "digest":
        _digest(user)
        claim = workers.NotificationDeliveryService()._claim_digest
    else:
        enqueue_event(
            NotificationEvent("notification.seen", "default", user_id=user.pk)
        )
        claim = OutboxDeliveryService().claim_one
    # SQLite cannot execute FOR UPDATE. Record the query contract here; the
    # PostgreSQL race tests exercise actual lock ownership and exclusion.
    with (
        patch.object(
            connection.features, "has_select_for_update_skip_locked", skip_locked
        ),
        patch.object(connection.features, "has_select_for_update", True),
        patch.object(
            QuerySet,
            "select_for_update",
            autospec=True,
            side_effect=lambda qs, **kwargs: qs,
        ) as locking,
    ):
        row = claim()
    assert row is not None
    locking.assert_called_once()
    assert locking.call_args.kwargs == ({"skip_locked": True} if skip_locked else {})


@pytest.mark.parametrize("kind", ["direct", "digest", "outbox"])
@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_compare_and_swap_claim_can_lose_race_without_owning_work(user, kind):
    if kind == "direct":
        _delivery(user)
        claim = workers.NotificationDeliveryService().claim_one
    elif kind == "digest":
        _digest(user)
        claim = workers.NotificationDeliveryService()._claim_digest
    else:
        enqueue_event(
            NotificationEvent("notification.seen", "default", user_id=user.pk)
        )
        claim = OutboxDeliveryService().claim_one
    original = QuerySet.update

    def update(queryset, **fields):
        if fields.get("status") == "PROCESSING":
            return 0
        return original(queryset, **fields)

    with patch.object(QuerySet, "update", autospec=True, side_effect=update):
        assert claim() is None


@pytest.mark.parametrize("failure", ["unsafe_code", "unexpected"])
@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_individual_provider_failure_retries_with_sanitized_metadata(
    user, failure, caplog
):
    job = _delivery(user)
    error = (
        DeliveryError("private email and credentials")
        if failure == "unsafe_code"
        else RuntimeError("private email and credentials")
    )
    if failure == "unsafe_code":
        error.code = "secret@example.org"
    backend = Mock()
    backend.send.side_effect = error
    with patch.object(workers, "load_backend", return_value=backend):
        assert workers.NotificationDeliveryService().process_next() == "retry"
    job.refresh_from_db()
    assert job.status == "PENDING"
    assert job.attempt_history.get().code == (
        "delivery_error" if failure == "unsafe_code" else "backend_error"
    )
    assert "private email" not in caplog.text


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_exhausted_digest_marks_pending_children_failed(user):
    digest, job = _digest(user, attempts=5)
    assert workers.NotificationDeliveryService()._claim_digest() is None
    digest.refresh_from_db()
    job.refresh_from_db()
    assert digest.status == job.status == "FAILED"
    assert digest.failed_at is not None and job.failed_at is not None


@pytest.mark.parametrize(
    "failure,attempts,expected",
    [
        (PermanentDeliveryError("private"), 0, "failed"),
        (DeliveryError("private"), 0, "retry"),
        (RuntimeError("private"), 0, "retry"),
        (DeliveryError("private"), 4, "failed"),
    ],
)
@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_digest_provider_failures_preserve_retry_policy(
    user, failure, attempts, expected, caplog
):
    digest, job = _digest(user, attempts=attempts)
    backend = Mock()
    backend.send_digest.side_effect = failure
    with patch.object(workers, "load_backend", return_value=backend):
        assert workers.NotificationDeliveryService().process_next_digest() == expected
    digest.refresh_from_db()
    job.refresh_from_db()
    assert digest.status == ("FAILED" if expected == "failed" else "PENDING")
    assert job.status == ("FAILED" if expected == "failed" else "PENDING")
    assert "private" not in caplog.text


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_digest_deferral_does_not_consume_attempt_and_stale_owner_cannot_finish(user):
    digest, job = _digest(user)
    _schedule(user)
    worker = workers.NotificationDeliveryService()
    until = timezone.now() + timedelta(hours=2)
    with patch.object(workers, "quiet_end_at", return_value=until):
        assert worker.process_next_digest() == "deferred"
    digest.refresh_from_db()
    assert digest.attempts == 0 and digest.available_at == until
    assert digest.status == "PENDING"
    assert worker._postpone_digest(digest, until) == "lost_lease"
    assert worker._finish_digest(digest, "delivered", [job]) == "lost_lease"
    NotificationDigest.objects.filter(pk=digest.pk).update(available_at=timezone.now())
    claimed = worker._claim_digest()
    assert worker._finish_digest(claimed, "deferred") == "deferred"
    digest.refresh_from_db()
    assert digest.status == "PROCESSING"  # _postpone_digest owns the state change.
    claimed.lease_token = uuid4()
    assert worker._finish_digest(claimed, "failed") == "lost_lease"


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_all_ineligible_first_digest_page_does_not_cancel_later_pending_jobs(user):
    digest, first = _digest(user)
    jobs = [first]
    for _ in range(50):
        job = _delivery(user)
        job.digest = digest
        jobs.append(job)
    NotificationDelivery.objects.bulk_update(jobs, ["digest"])
    with patch.object(workers, "notification_visible", return_value=(True, False)):
        assert (
            workers.NotificationDeliveryService().process_next_digest() == "delivered"
        )
    digest.refresh_from_db()
    assert digest.status == "PENDING"
    assert digest.deliveries.filter(status="CANCELLED").count() == 50
    assert digest.deliveries.filter(status="PENDING").count() == 1


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_process_batch_counts_completed_work(user):
    _delivery(user)
    with patch.object(workers, "load_backend", return_value=Mock()):
        counts = workers.NotificationDeliveryService().process_batch(2)
    assert counts["delivered"] == 1
    assert sum(counts.values()) == 1
    with pytest.raises(ValueError, match="limit"):
        OutboxDeliveryService().process_batch(0)
