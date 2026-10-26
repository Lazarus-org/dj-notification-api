"""Focused delivery creation, isolation, retries, privacy and recovery tests."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from django_notification.delivery import (
    connect_notification_delivery,
    disconnect_notification_delivery,
)
from django_notification.delivery.service import (
    NotificationDeliveryService,
    enqueue_notification_deliveries,
)
from django_notification.models import Notification
from django_notification.models.notification_delivery import (
    AttemptStatus,
    DeliveryStatus,
    NotificationDelivery,
    NotificationDeliveryAttempt,
)
from django_notification.outbox import OutboxDeliveryService

pytestmark = pytest.mark.django_db

EMAIL_BACKENDS = {
    "email": "django_notification.delivery.backends.DjangoEmailBackend",
}
MULTI_BACKENDS = {
    "email": "django_notification.delivery.backends.DjangoEmailBackend",
    "webhook": "django_notification.delivery.backends.SignedWebhookBackend",
}
SETTINGS = override_settings(
    DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox",
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS=EMAIL_BACKENDS,
)


@pytest.fixture
def registered():
    """Register durable fan-out and reliably remove the signal receiver."""
    with override_settings(
        DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox",
        DJANGO_NOTIFICATION_DELIVERY_BACKENDS=EMAIL_BACKENDS,
    ):
        connect_notification_delivery()
        try:
            yield
        finally:
            disconnect_notification_delivery()


def test_disabled_by_default_does_not_create_delivery_jobs(user):
    """The core package does not schedule external communication by default."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="Inbox only",
        recipients=[user],
        is_sent=True,
    )
    assert NotificationDelivery.objects.filter(notification=item).count() == 0


@SETTINGS
def test_outbox_event_materializes_jobs_once_on_replay(user, registered):
    """Reprocessing one outbox event never doubles a recipient/channel job."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="New item",
        recipients=[user],
        is_sent=True,
    )
    assert NotificationDelivery.objects.count() == 0
    assert OutboxDeliveryService().process_next() == "delivered"
    assert NotificationDelivery.objects.count() == 1
    assert enqueue_notification_deliveries(item.pk) == 1
    assert NotificationDelivery.objects.count() == 1


@SETTINGS
def test_rollbacks_do_not_leave_outbox_or_delivery_rows(user, registered):
    """Business transaction rollback eliminates external delivery intent."""
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            Notification.objects.create_notification(
                actor=user,
                verb="Rollback",
                recipients=[user],
                is_sent=True,
            )
            raise RuntimeError("rollback")
    assert NotificationDelivery.objects.count() == 0


@SETTINGS
def test_unsent_notifications_wait_for_transition(user, registered):
    """Only the first publish transition enqueues external jobs."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="Draft",
        recipients=[user],
        is_sent=False,
    )
    assert OutboxDeliveryService().process_next() == "delivered"
    assert NotificationDelivery.objects.count() == 0
    Notification.objects.update_notification(item.pk, is_sent=True)
    assert OutboxDeliveryService().process_batch(limit=10)["delivered"] == 2
    assert NotificationDelivery.objects.count() == 1


@SETTINGS
def test_group_members_are_eligible_but_unrelated_staff_is_not(
    user, another_user, admin_user, registered
):
    """Group targeting, not elevated staff status, defines the audience."""
    managers = Group.objects.create(name="Managers-delivery")
    user.groups.add(managers)
    item = Notification.objects.create_notification(
        actor=admin_user,
        verb="Group message",
        groups=[managers],
        is_sent=True,
    )
    assert OutboxDeliveryService().process_next() == "delivered"
    assert list(
        NotificationDelivery.objects.filter(notification=item).values_list(
            "recipient_id", flat=True
        )
    ) == [user.pk]


@SETTINGS
def test_bulk_sent_materializes_only_targeted_jobs(
    user, another_user, registered, monkeypatch
):
    """Bulk transitions retain IDs across pages without sending other drafts."""
    from django_notification.services import notification as lifecycle

    monkeypatch.setattr(lifecycle, "_BATCH_SIZE", 2)
    items = [
        Notification.objects.create_notification(
            actor=user,
            verb=f"Draft {number}",
            recipients=[user],
        )
        for number in range(5)
    ]
    other = Notification.objects.create_notification(
        actor=user,
        verb="Other draft",
        recipients=[another_user],
    )
    assert Notification.objects.mark_all_as_sent(recipients=[user]) == 5
    assert Notification.objects.mark_all_as_sent(recipients=[user]) == 0
    assert OutboxDeliveryService().process_batch(limit=100)["delivered"] == 12
    assert set(
        NotificationDelivery.objects.values_list("notification_id", "recipient_id")
    ) == {(item.pk, user.pk) for item in items}
    other.refresh_from_db()
    assert not other.is_sent


@SETTINGS
def test_bulk_sent_rollback_discards_all_intent(user, registered):
    """Sending and durable per-row events share the source transaction."""
    from django_notification.models.notification_outbox_event import (
        NotificationOutboxEvent,
    )

    item = Notification.objects.create_notification(
        actor=user,
        verb="Rollback bulk",
        recipients=[user],
    )
    before = NotificationOutboxEvent.objects.count()
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            Notification.objects.mark_all_as_sent(recipients=[user])
            raise RuntimeError("rollback")
    item.refresh_from_db()
    assert not item.is_sent
    assert NotificationOutboxEvent.objects.count() == before


@SETTINGS
def test_dedupe_overlap_between_direct_and_group(user, registered):
    """One user targeted twice receives one job for the same channel."""
    managers = Group.objects.create(name="Managers-overlap-delivery")
    user.groups.add(managers)
    Notification.objects.create_notification(
        actor=user,
        verb="Overlap",
        recipients=[user],
        groups=[managers],
        is_sent=True,
    )
    assert OutboxDeliveryService().process_next() == "delivered"
    assert NotificationDelivery.objects.count() == 1


@SETTINGS
def test_success_records_single_attempt_with_sanitized_code(user, registered):
    """Backend call succeeds without persisting recipient email or content."""
    Notification.objects.create_notification(
        actor=user,
        verb="Welcome",
        recipients=[user],
        is_sent=True,
    )
    OutboxDeliveryService().process_next()
    with patch(
        "django_notification.delivery.backends.send_mail", return_value=1
    ) as mail:
        assert NotificationDeliveryService().process_next() == "delivered"
    assert mail.call_count == 1
    row = NotificationDelivery.objects.get()
    assert row.status == DeliveryStatus.DELIVERED
    attempt = NotificationDeliveryAttempt.objects.get()
    assert (attempt.number, attempt.status, attempt.code) == (
        1,
        AttemptStatus.SUCCEEDED,
        "accepted",
    )
    assert "testuser@example.com" not in str(attempt.__dict__)


@SETTINGS
def test_transient_error_is_retried_and_attempt_history_is_kept(user, registered):
    """One retryable error cannot destroy the per-channel attempt log."""
    Notification.objects.create_notification(
        actor=user,
        verb="Retry",
        recipients=[user],
        is_sent=True,
    )
    OutboxDeliveryService().process_next()
    worker = NotificationDeliveryService(retry_base_seconds=1)
    with patch("django_notification.delivery.backends.send_mail", side_effect=OSError):
        assert worker.process_next() == "retry"
    row = NotificationDelivery.objects.get()
    assert row.attempts == 1
    NotificationDelivery.objects.filter(pk=row.pk).update(
        available_at=timezone.now() - timedelta(seconds=1),
    )
    with patch("django_notification.delivery.backends.send_mail", return_value=1):
        assert worker.process_next() == "delivered"
    assert list(
        NotificationDeliveryAttempt.objects.order_by("number").values_list(
            "number", "status"
        )
    ) == [
        (1, AttemptStatus.RETRY),
        (2, AttemptStatus.SUCCEEDED),
    ]


@SETTINGS
def test_group_departure_cancels_a_queued_delivery(user, registered):
    """Dynamic membership is rechecked before any external communication."""
    group = Group.objects.create(name="Managers-revoked-delivery")
    user.groups.add(group)
    Notification.objects.create_notification(
        actor=user,
        verb="Revoked",
        groups=[group],
        is_sent=True,
    )
    OutboxDeliveryService().process_next()
    user.groups.remove(group)
    with patch("django_notification.delivery.backends.send_mail") as mail:
        assert NotificationDeliveryService().process_next() == "cancelled"
    mail.assert_not_called()
    assert NotificationDeliveryAttempt.objects.count() == 0


@override_settings(
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS=MULTI_BACKENDS,
    DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox",
)
def test_channel_failure_is_independent_of_other_channels(user):
    """Permanent webhook failure does not block a successful email send."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="Multi",
        recipients=[user],
        is_sent=True,
    )
    enqueue_notification_deliveries(item.pk)
    worker = NotificationDeliveryService()
    with patch("django_notification.delivery.backends.send_mail", return_value=1):
        assert worker.process_next() == "delivered"
    assert worker.process_next() == "failed"  # webhook is not configured
    assert dict(NotificationDelivery.objects.values_list("channel", "status")) == {
        "email": DeliveryStatus.DELIVERED,
        "webhook": DeliveryStatus.FAILED,
    }


@SETTINGS
def test_manual_requeue_preserves_monotonic_attempt_numbers(user):
    """Requeue does not overwrite or delete previous failed attempt records."""
    notification = Notification.objects.create_notification(
        actor=user,
        verb="Retry again",
        recipients=[user],
        is_sent=True,
    )
    enqueue_notification_deliveries(notification.pk)
    worker = NotificationDeliveryService(max_attempts=1)
    with patch("django_notification.delivery.backends.send_mail", side_effect=OSError):
        assert worker.process_next() == "failed"
    delivery = NotificationDelivery.objects.get()
    call_command("requeue_notification_deliveries", str(delivery.pk))
    with patch("django_notification.delivery.backends.send_mail", return_value=1):
        assert worker.process_next() == "delivered"
    assert list(
        NotificationDeliveryAttempt.objects.order_by("number").values_list(
            "number", flat=True
        )
    ) == [1, 2]


@override_settings(
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS={"sms": "bad.module.Backend"},
    DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox",
)
def test_unimportable_backend_rejected_at_registration():
    """A broken integration configuration fails early, not on first delivery."""
    with pytest.raises(ImproperlyConfigured):
        connect_notification_delivery()


@SETTINGS
def test_optional_category_preference_blocks_external_enqueuing(user):
    """Disabled nonmandatory categories must not contact external providers."""
    from django_notification.models import (
        NotificationCategory,
        NotificationPreference,
    )

    category = NotificationCategory.objects.create(
        slug="optional-ext",
        name="Optional external",
    )
    NotificationPreference.objects.create(
        user=user,
        category=category,
        enabled=False,
    )
    notification = Notification.objects.create_notification(
        actor=user,
        verb="Opt out",
        recipients=[user],
        is_sent=True,
        category=category.slug,
    )
    assert enqueue_notification_deliveries(notification.pk) == 0
    assert NotificationDelivery.objects.count() == 0


@SETTINGS
def test_mandatory_category_still_enqueues_when_override_is_disabled(user):
    """Mandatory categories cannot be suppressed by stale preference rows."""
    from django_notification.models import (
        NotificationCategory,
        NotificationPreference,
    )

    category = NotificationCategory.objects.create(
        slug="mandatory-ext",
        name="Mandatory external",
        is_mandatory=True,
    )
    NotificationPreference.objects.create(
        user=user,
        category=category,
        enabled=False,
    )
    notification = Notification.objects.create_notification(
        actor=user,
        verb="Mandatory",
        recipients=[user],
        is_sent=True,
        category=category.slug,
    )
    assert enqueue_notification_deliveries(notification.pk) == 1
    assert NotificationDelivery.objects.count() == 1


@SETTINGS
def test_stale_lease_cannot_acknowledge_a_reclaimed_delivery(user):
    """Old process must not mark a newer owner's claim delivered."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="Lease",
        recipients=[user],
        is_sent=True,
    )
    enqueue_notification_deliveries(item.pk)
    worker = NotificationDeliveryService()
    old_claim = worker.claim_one()
    NotificationDelivery.objects.filter(pk=old_claim.pk).update(
        leased_until=timezone.now() - timedelta(seconds=1),
    )
    new_claim = worker.claim_one()
    assert new_claim.lease_token != old_claim.lease_token
    assert (
        worker._finish(old_claim, AttemptStatus.SUCCEEDED, "accepted") == "lost_lease"
    )
    assert NotificationDeliveryAttempt.objects.count() == 0
    assert worker._finish(new_claim, AttemptStatus.SUCCEEDED, "accepted") == "delivered"
