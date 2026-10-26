"""Phase 16: time zones, quiet hours, digest aggregation and safety."""

from datetime import datetime, time, timedelta, timezone as utc_timezone
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from django_notification.delivery.scheduling import (
    next_digest_at,
    quiet_end_at,
)
from django_notification.delivery.service import (
    NotificationDeliveryService,
    enqueue_notification_deliveries,
)
from django_notification.models import (
    Notification,
    NotificationDelivery,
    NotificationDeliverySchedule,
    NotificationDigest,
    NotificationCategory,
)
from django_notification.models.notification_delivery import DeliveryStatus
from django_notification.models.notification_delivery_schedule import (
    DeliveryFrequency,
)

pytestmark = pytest.mark.django_db
BACKENDS = {"email": "django_notification.delivery.backends.DjangoEmailBackend"}


def _created(user, *, category="general", priority="NORMAL"):
    return Notification.objects.create_notification(
        actor=user,
        recipients=[user],
        verb="Alert",
        description="Test message",
        category=category,
        priority=priority,
        is_sent=True,
    )


def _schedule(user, **fields):
    return NotificationDeliverySchedule.objects.create(
        user=user,
        channel="email",
        **fields,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_quiet_window_crossing_midnight(user):
    """Quiet-hour calculations use local time, including midnight rollover."""
    setting = _schedule(
        user,
        timezone="UTC",
        quiet_start=time(22),
        quiet_end=time(7),
    )
    now = datetime(2026, 10, 26, 23, tzinfo=utc_timezone.utc)
    assert quiet_end_at(now, setting) == datetime(
        2026,
        10,
        27,
        7,
        tzinfo=utc_timezone.utc,
    )
    now = datetime(2026, 10, 26, 12, tzinfo=utc_timezone.utc)
    assert quiet_end_at(now, setting) == now


def test_next_digest_slots_respect_time_zone(user):
    """Local Monday and daily 09:00 are converted to UTC safely."""
    setting = _schedule(
        user,
        frequency=DeliveryFrequency.DAILY,
        timezone="America/Los_Angeles",
    )
    now = datetime(2026, 10, 26, 12, tzinfo=utc_timezone.utc)
    assert next_digest_at(now, setting) == datetime(
        2026,
        10,
        27,
        16,
        tzinfo=utc_timezone.utc,
    )
    setting.frequency = DeliveryFrequency.WEEKLY
    assert next_digest_at(now, setting) == datetime(
        2026,
        11,
        2,
        17,
        tzinfo=utc_timezone.utc,
    )


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_queued_email_digest_reuses_envelope(user):
    """Multiple notifications in the same local day share a single batch."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    first = _created(user)
    second = _created(user)
    assert enqueue_notification_deliveries(first.pk) == 1
    assert enqueue_notification_deliveries(second.pk) == 1
    assert NotificationDigest.objects.count() == 1
    rows = NotificationDelivery.objects.order_by("pk")
    assert rows.count() == 2
    assert rows[0].digest_id == rows[1].digest_id
    assert rows[0].available_at > timezone.now()


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_email_digest_sends_once_for_multiple_jobs(user):
    """One accepted email marks the selected individual delivery rows."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    for _ in range(2):
        enqueue_notification_deliveries(_created(user).pk)
    envelope = NotificationDigest.objects.get()
    NotificationDigest.objects.filter(pk=envelope.pk).update(
        available_at=timezone.now() - timedelta(minutes=1),
    )
    with patch(
        "django_notification.delivery.backends.send_mail",
        return_value=1,
    ) as mail:
        assert NotificationDeliveryService().process_next() == "delivered"
    assert mail.call_count == 1
    assert "2 updates" in mail.call_args.args[0]
    assert (
        NotificationDelivery.objects.filter(
            status=DeliveryStatus.DELIVERED,
        ).count()
        == 2
    )


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_digest_replay_does_not_duplicate_jobs_or_email(user):
    """Replay of the outbox materialization is harmless after a digest send."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    item = _created(user)
    enqueue_notification_deliveries(item.pk)
    enqueue_notification_deliveries(item.pk)
    assert NotificationDelivery.objects.count() == 1
    NotificationDigest.objects.update(available_at=timezone.now() - timedelta(1))
    with patch(
        "django_notification.delivery.backends.send_mail",
        return_value=1,
    ) as mail:
        assert NotificationDeliveryService().process_next() == "delivered"
        assert NotificationDeliveryService().process_next() == "empty"
    assert mail.call_count == 1


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_urgent_and_mandatory_messages_bypass_scheduling(user):
    """Urgent priority or mandatory category always receives immediate jobs."""
    _schedule(
        user,
        frequency=DeliveryFrequency.DAILY,
        quiet_start=time(0),
        quiet_end=time(23, 59),
    )
    mandatory = NotificationCategory.objects.create(
        slug="mandatory_message",
        name="Mandatory",
        is_mandatory=True,
    )
    urgent = _created(user, priority="URGENT")
    required = _created(user, category=mandatory.pk)
    enqueue_notification_deliveries(urgent.pk)
    enqueue_notification_deliveries(required.pk)
    assert NotificationDelivery.objects.filter(digest__isnull=True).count() == 2


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_quiet_hours_defer_immediate_job_without_consuming_attempt(user):
    """A provider call during quiet time is deferred, not counted as a retry."""
    now = timezone.now()
    local = now.astimezone(utc_timezone.utc).time().replace(tzinfo=None)
    start = (datetime.combine(now.date(), local) - timedelta(hours=1)).time()
    end = (datetime.combine(now.date(), local) + timedelta(hours=1)).time()
    _schedule(user, quiet_start=start, quiet_end=end)
    item = _created(user)
    enqueue_notification_deliveries(item.pk)
    NotificationDelivery.objects.update(available_at=now - timedelta(seconds=1))
    with patch("django_notification.delivery.backends.send_mail") as mail:
        assert NotificationDeliveryService().process_next() == "deferred"
    mail.assert_not_called()
    job = NotificationDelivery.objects.get()
    assert job.attempts == 0
    assert job.retry_attempts == 0
    assert job.available_at > now


def test_schedule_api_is_per_user_and_rejects_nonemail_digest(user, another_user):
    """An authenticated client cannot set another user's preferences."""
    url = reverse(
        "notifications-set-delivery-schedule",
        kwargs={
            "channel": "email",
        },
    )
    response = _client(user).put(
        url,
        {
            "frequency": "DAILY",
            "timezone": "UTC",
            "quiet_start": "22:00",
            "quiet_end": "07:00",
        },
        format="json",
    )
    assert response.status_code == 200
    assert NotificationDeliverySchedule.objects.filter(user=user).exists()
    assert not NotificationDeliverySchedule.objects.filter(
        user=another_user,
    ).exists()
    sms = reverse(
        "notifications-set-delivery-schedule",
        kwargs={
            "channel": "sms",
        },
    )
    assert (
        _client(user)
        .put(
            sms,
            {
                "frequency": "WEEKLY",
                "timezone": "UTC",
            },
            format="json",
        )
        .status_code
        == 400
    )


def test_bad_timezone_and_partial_quiet_hours_are_rejected(user):
    """Reject misconfigured delivery policies before persisting them."""
    url = reverse(
        "notifications-set-delivery-schedule",
        kwargs={
            "channel": "email",
        },
    )
    client = _client(user)
    assert (
        client.put(
            url,
            {
                "frequency": "IMMEDIATE",
                "timezone": "Not/AZone",
            },
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.put(
            url,
            {
                "frequency": "IMMEDIATE",
                "timezone": "UTC",
                "quiet_start": "23:00",
            },
            format="json",
        ).status_code
        == 400
    )


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_failed_digest_recovery_keeps_children(user):
    """A failed digest may be explicitly requeued with its pending jobs."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    enqueue_notification_deliveries(_created(user).pk)
    batch = NotificationDigest.objects.get()
    NotificationDigest.objects.update(
        status=DeliveryStatus.FAILED,
        failed_at=timezone.now(),
        attempts=5,
    )
    NotificationDelivery.objects.update(status=DeliveryStatus.FAILED)
    call_command("requeue_notification_digests", batch.pk)
    batch.refresh_from_db()
    assert batch.status == DeliveryStatus.PENDING
    assert NotificationDelivery.objects.get().status == DeliveryStatus.PENDING


def test_ambiguous_fall_back_quiet_end_uses_second_occurrence(user):
    """Do not postpone a fall-back quiet window until the following day."""
    from zoneinfo import ZoneInfo

    setting = _schedule(
        user,
        timezone="America/Los_Angeles",
        quiet_start=time(0, 30),
        quiet_end=time(1, 30),
    )
    # Nov 1 2026, 01:15 PST (the second 01:15 of the day).
    second_fold = datetime(
        2026,
        11,
        1,
        1,
        15,
        tzinfo=ZoneInfo("America/Los_Angeles"),
        fold=1,
    ).astimezone(utc_timezone.utc)
    expected = datetime(2026, 11, 1, 9, 30, tzinfo=utc_timezone.utc)
    assert quiet_end_at(second_fold, setting) == expected


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_preference_opt_out_cancels_email_digest_before_send(user):
    """Opting out after enqueue prevents the batched provider call."""
    from django_notification.models import NotificationChannelPreference

    _schedule(user, frequency=DeliveryFrequency.DAILY)
    item = _created(user)
    enqueue_notification_deliveries(item.pk)
    NotificationChannelPreference.objects.create(
        user=user,
        category=item.category,
        channel="email",
        enabled=False,
    )
    NotificationDigest.objects.update(available_at=timezone.now() - timedelta(1))
    with patch("django_notification.delivery.backends.send_mail") as mail:
        assert NotificationDeliveryService().process_next() == "cancelled"
    mail.assert_not_called()
    assert NotificationDelivery.objects.get().status == DeliveryStatus.CANCELLED


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_switching_cadence_does_not_orphan_an_immediate_job(user):
    """New digest preferences do not silently reroute already queued jobs."""
    item = _created(user)
    enqueue_notification_deliveries(item.pk)
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    with patch(
        "django_notification.delivery.backends.send_mail",
        return_value=1,
    ) as mail:
        assert NotificationDeliveryService().process_next() == "delivered"
    assert mail.call_count == 1
    assert NotificationDigest.objects.count() == 0


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_late_digest_fanout_reopens_completed_slot_without_resending(user):
    """Late children remain reachable after a worker completed their slot."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    now = timezone.now()
    first, second = _created(user), _created(user)
    with patch(
        "django_notification.delivery.service.schedule_for", return_value=(now, now)
    ):
        enqueue_notification_deliveries(first.pk)
        with patch(
            "django_notification.delivery.backends.send_mail", return_value=1
        ) as mail:
            assert NotificationDeliveryService().process_next_digest() == "delivered"
            enqueue_notification_deliveries(first.pk)
            assert NotificationDigest.objects.get().status == DeliveryStatus.DELIVERED
            enqueue_notification_deliveries(second.pk)
            assert NotificationDigest.objects.get().status == DeliveryStatus.PENDING
            assert NotificationDeliveryService().process_next_digest() == "delivered"
        assert mail.call_count == 2
    assert (
        NotificationDelivery.objects.filter(status=DeliveryStatus.DELIVERED).count()
        == 2
    )


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_late_digest_fanout_preserves_terminal_retry_budget(user):
    """A failed slot requires explicit requeue, including its late children."""
    _schedule(user, frequency=DeliveryFrequency.DAILY)
    now = timezone.now()
    with patch(
        "django_notification.delivery.service.schedule_for", return_value=(now, now)
    ):
        enqueue_notification_deliveries(_created(user).pk)
        NotificationDigest.objects.update(
            status=DeliveryStatus.FAILED, failed_at=now, attempts=5
        )
        NotificationDelivery.objects.update(status=DeliveryStatus.FAILED, failed_at=now)
        enqueue_notification_deliveries(_created(user).pk)
    assert (
        NotificationDelivery.objects.filter(status=DeliveryStatus.FAILED).count() == 2
    )
    assert NotificationDeliveryService().process_next_digest() == "empty"
    call_command("requeue_notification_digests", NotificationDigest.objects.get().pk)
    assert (
        NotificationDelivery.objects.filter(status=DeliveryStatus.PENDING).count() == 2
    )
