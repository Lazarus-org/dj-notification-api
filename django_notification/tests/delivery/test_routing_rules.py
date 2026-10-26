"""Phase 18: deterministic rules, secure overrides and queued-job revocation."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import override_settings

from django_notification.delivery.routing import routed_channels
from django_notification.delivery.service import (
    NotificationDeliveryService,
    enqueue_notification_deliveries,
)
from django_notification.models import (
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationRoutingRule,
)
from django_notification.models.notification_delivery import DeliveryStatus
from django_notification.models.notification_routing_rule import RoutingAction

pytestmark = pytest.mark.django_db

BACKENDS = {
    "email": "django_notification.delivery.backends.DjangoEmailBackend",
    "sms": "django_notification.delivery.backends.DjangoEmailBackend",
    "push": "django_notification.delivery.backends.DjangoEmailBackend",
}


def _notification(user, **kwargs):
    """Create a private notification for one recipient."""
    return Notification.objects.create_notification(
        actor=user,
        verb="Routing test",
        recipients=[user],
        is_sent=True,
        **kwargs,
    )


def _rule(name="Routing rule", **kwargs):
    """Create an operator rule with explicit actions."""
    return NotificationRoutingRule.objects.create(
        name=name,
        action=RoutingAction.REPLACE,
        channels=["email"],
        **kwargs,
    )


def test_no_rules_preserve_all_configured_channels(user):
    """Existing installations retain the Phase 14 default."""
    item = _notification(user)
    assert routed_channels(item, ("email", "sms")) == ("email", "sms")


def test_replace_rules_filter_delivery_before_jobs_are_created(user):
    """Enqueue only channels present in the resolved server policy."""
    item = _notification(user)
    _rule()
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS):
        assert enqueue_notification_deliveries(item.pk) == 1
    assert list(
        NotificationDelivery.objects.values_list(
            "channel",
            flat=True,
        )
    ) == ["email"]


def test_high_priority_adds_channels_without_mutating_priority(user):
    """High-priority escalation affects channels, not the source record."""
    _rule(sort_order=10)
    NotificationRoutingRule.objects.create(
        name="Escalate to SMS",
        sort_order=20,
        action=RoutingAction.ADD,
        channels=["sms"],
        min_priority="HIGH",
        max_priority="URGENT",
    )
    normal = _notification(user)
    high = _notification(user, priority="HIGH")
    configured = ("email", "sms", "push")
    assert routed_channels(normal, configured) == ("email",)
    assert routed_channels(high, configured) == ("email", "sms")
    high.refresh_from_db()
    assert high.priority == "HIGH"


def test_specific_rule_overrides_global_at_same_order(user):
    """Category-specific conditions apply after global conditions in ties."""
    _rule(sort_order=5)
    alerts = NotificationCategory.objects.create(
        slug="routing_alerts",
        name="Routing alerts",
    )
    NotificationRoutingRule.objects.create(
        name="Alert push",
        category=alerts,
        sort_order=5,
        action=RoutingAction.REPLACE,
        channels=["push"],
    )
    general = _notification(user)
    alert = _notification(user, category=alerts.pk)
    configured = ("email", "push")
    assert routed_channels(general, configured) == ("email",)
    assert routed_channels(alert, configured) == ("push",)


def test_status_condition_and_remove_are_deterministic(user):
    """A restrictive match cannot accidentally match another status."""
    NotificationRoutingRule.objects.create(
        name="Suppress SMS for errors",
        action=RoutingAction.REMOVE,
        channels=["sms"],
        notification_status="ERROR",
    )
    info = _notification(user, status="INFO")
    error = _notification(user, status="ERROR")
    channels = ("email", "sms")
    assert routed_channels(info, channels) == channels
    assert routed_channels(error, channels) == ("email",)


def test_routing_never_enables_an_unconfigured_backend(user):
    """Provider registration is an unconditional upper bound."""
    NotificationRoutingRule.objects.create(
        name="Only unconfigured SMS",
        action=RoutingAction.REPLACE,
        channels=["sms"],
    )
    item = _notification(user)
    assert routed_channels(item, ("email",)) == ()


def test_invalid_rules_are_rejected_and_corrupt_rows_fail_closed(user):
    """Programmatic writes validate; bad persisted data never widens sends."""
    with pytest.raises(ValidationError):
        NotificationRoutingRule.objects.create(
            name="Invalid",
            action=RoutingAction.ADD,
            channels=["unknown"],
        )
    item = _notification(user)
    rule = _rule()
    NotificationRoutingRule.objects.filter(pk=rule.pk).update(
        channels=["not-a-channel"],
    )
    with pytest.raises(ImproperlyConfigured):
        routed_channels(item, ("email", "sms"))


@override_settings(
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS={
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
)
def test_disabling_route_cancels_queued_job_before_backend_call(user):
    """Stale jobs cannot bypass a routing change made after enqueue."""
    item = _notification(user)
    assert enqueue_notification_deliveries(item.pk) == 1
    NotificationRoutingRule.objects.create(
        name="No email",
        action=RoutingAction.REMOVE,
        channels=["email"],
    )
    with patch("django_notification.delivery.backends.send_mail") as send:
        assert NotificationDeliveryService().process_next() == "cancelled"
    send.assert_not_called()
    assert NotificationDelivery.objects.get().status == DeliveryStatus.CANCELLED


def test_deactivated_rule_is_ignored(user):
    """Operators can safely pause rules without deleting configuration."""
    _rule(enabled=False)
    item = _notification(user)
    assert routed_channels(item, ("email", "sms")) == ("email", "sms")


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_rules_cannot_override_a_users_channel_opt_out(user):
    """Even explicitly added channels remain subject to user preferences."""
    from django_notification.models import NotificationChannelPreference

    item = _notification(user)
    NotificationRoutingRule.objects.create(
        name="Prefer all",
        action=RoutingAction.REPLACE,
        channels=["email", "sms"],
    )
    NotificationChannelPreference.objects.create(
        user=user,
        category_id="general",
        channel="sms",
        enabled=False,
    )
    enqueue_notification_deliveries(item.pk)
    assert set(
        NotificationDelivery.objects.values_list(
            "channel",
            flat=True,
        )
    ) == {"email"}


@override_settings(
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS={
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
)
def test_pending_digest_drops_channel_revoked_by_rule(user):
    """Digest workers also re-check current route before sending content."""
    from django_notification.models import (
        NotificationDeliverySchedule,
        NotificationDigest,
    )
    from django_notification.models.notification_delivery_schedule import (
        DeliveryFrequency,
    )
    from datetime import timedelta
    from django.utils import timezone

    NotificationDeliverySchedule.objects.create(
        user=user,
        channel="email",
        frequency=DeliveryFrequency.DAILY,
    )
    item = _notification(user)
    assert enqueue_notification_deliveries(item.pk) == 1
    NotificationDigest.objects.update(
        available_at=timezone.now() - timedelta(minutes=1),
    )
    NotificationRoutingRule.objects.create(
        name="Disable digest email",
        action=RoutingAction.REMOVE,
        channels=["email"],
    )
    with patch("django_notification.delivery.backends.send_mail") as send:
        assert NotificationDeliveryService().process_next() == "cancelled"
    send.assert_not_called()
    assert NotificationDelivery.objects.get().status == DeliveryStatus.CANCELLED


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_enabling_later_route_does_not_backfill_prior_jobs(user):
    """Policy changes are not a trigger for old-notification broadcasting."""
    rule = _rule()
    item = _notification(user)
    enqueue_notification_deliveries(item.pk)
    rule.channels = ["email", "sms"]
    rule.save()
    assert list(
        NotificationDelivery.objects.values_list(
            "channel",
            flat=True,
        )
    ) == ["email"]


def test_invalid_persisted_status_cannot_widen_routes(user):
    """A corrupt status condition is treated as broken policy, not no rule."""
    rule = _rule()
    NotificationRoutingRule.objects.filter(pk=rule.pk).update(
        notification_status="NOT_REAL",
    )
    with pytest.raises(ImproperlyConfigured):
        routed_channels(_notification(user), ("email", "sms"))
