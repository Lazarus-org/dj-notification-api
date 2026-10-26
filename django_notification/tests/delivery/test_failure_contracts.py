"""Exercise adapter boundaries with malformed configuration and provider failures."""

from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import override_settings

from django_notification.delivery import backends, registry, rendering, scheduling
from django_notification.delivery.routing import routed_channels
from django_notification.models import NotificationTemplate
from django_notification.models.notification_delivery_schedule import (
    NotificationDeliverySchedule,
)
from django_notification.models.notification_routing_rule import NotificationRoutingRule
from django_notification.models.notification_template import validate_message_template
from django_notification.tests.delivery.test_templates_preferences import _delivery

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("mapping", [[], {"fax": "x"}, {"email": ""}, {"email": None}])
def test_invalid_backend_mapping(mapping):
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=mapping):
        with pytest.raises(ImproperlyConfigured):
            registry.backend_paths()


def test_backend_registration_rejects_disabled_wrong_type_and_constructor():
    with pytest.raises(ImproperlyConfigured, match="not enabled"):
        registry.load_backend("email")
    with override_settings(
        DJANGO_NOTIFICATION_DELIVERY_BACKENDS={"email": "fake.Backend"}
    ):
        for cls in (object, backends.DeliveryBackend()):
            with patch.object(registry, "import_string", return_value=cls):
                with pytest.raises(ImproperlyConfigured, match="must extend"):
                    registry.load_backend("email")

        class BrokenBackend(backends.DeliveryBackend):
            def __init__(self):
                raise RuntimeError("private configuration")

        with patch.object(registry, "import_string", return_value=BrokenBackend):
            with pytest.raises(ImproperlyConfigured, match="construction failed"):
                registry.load_backend("email")
    with pytest.raises(ImproperlyConfigured, match="outbox"):
        registry.connect_notification_delivery()
    with override_settings(DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox"):
        with pytest.raises(ImproperlyConfigured, match="at least one"):
            registry.connect_notification_delivery()


def test_base_adapter_contract():
    with pytest.raises(NotImplementedError):
        backends.DeliveryBackend().send(None, idempotency_key="test")
    with pytest.raises(backends.PermanentDeliveryError, match="unsupported"):
        backends.DeliveryBackend().send_digest(None, [], idempotency_key="test")


@pytest.mark.parametrize("size", [0, 51])
def test_digest_adapter_bounds(size):
    with pytest.raises(backends.PermanentDeliveryError, match="batch size"):
        backends.DjangoEmailBackend().send_digest(
            None, [None] * size, idempotency_key="test"
        )


def test_digest_adapter_recipient_validation(user):
    delivery = _delivery(user)
    backend = backends.DjangoEmailBackend()
    with pytest.raises(backends.PermanentDeliveryError, match="inconsistent"):
        backend.send_digest(
            SimpleNamespace(recipient_id=user.pk + 1),
            [delivery],
            idempotency_key="test",
        )
    user.email = " "
    delivery.recipient = user
    with pytest.raises(backends.PermanentDeliveryError, match="no email"):
        backend.send_digest(
            SimpleNamespace(recipient_id=user.pk), [delivery], idempotency_key="test"
        )


@pytest.mark.parametrize("digest", [False, True])
@pytest.mark.parametrize("failure", ["template", "exception", "rejected"])
def test_email_adapter_sanitizes_failures(user, digest, failure):
    delivery = _delivery(user)
    backend = backends.DjangoEmailBackend()
    render = Mock(return_value=rendering.RenderedMessage("Title", "Body", "en"))
    send = Mock(return_value=1)
    if failure == "template":
        render.side_effect = ValidationError("private text")
    elif failure == "exception":
        send.side_effect = RuntimeError("secret credential")
    else:
        send.return_value = 0
    expected = (
        backends.PermanentDeliveryError
        if failure == "template"
        else backends.RetryableDeliveryError
    )
    with (
        patch.object(backends, "render_delivery", render),
        patch.object(backends, "send_mail", send),
    ):
        with pytest.raises(expected) as error:
            if digest:
                backend.send_digest(
                    SimpleNamespace(recipient_id=user.pk),
                    [delivery],
                    idempotency_key="stable",
                )
            else:
                backend.send(delivery, idempotency_key="stable")
    assert "private" not in str(error.value)
    assert "secret" not in str(error.value)


@override_settings(
    DJANGO_NOTIFICATION_WEBHOOK_URL="https://example.org/hook",
    DJANGO_NOTIFICATION_WEBHOOK_SECRET="test",
)
def test_webhook_non_success_response_retries(user):
    response = Mock(status=503)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch.object(backends, "build_opener") as opener:
        opener.return_value.open.return_value = response
        with pytest.raises(backends.RetryableDeliveryError, match="unsuccessful"):
            backends.SignedWebhookBackend().send(
                _delivery(user), idempotency_key="stable"
            )


@override_settings(DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE="../bad")
def test_rendering_rejects_invalid_default_even_with_user_locale(user):
    user.language_code = "en"
    with pytest.raises(ImproperlyConfigured):
        rendering.delivery_locale(user)
    with patch.object(rendering, "delivery_locale", return_value="en"):
        with pytest.raises(ImproperlyConfigured):
            rendering.render_delivery(_delivery(user))


def test_persisted_blank_template_fails_closed(user):
    delivery = _delivery(user)
    NotificationTemplate.objects.create(
        category=delivery.notification.category,
        channel="email",
        locale="en-us",
        body=" ",
    )
    with pytest.raises(ValidationError, match="blank"):
        rendering.render_delivery(delivery)


def test_template_validation_boundary():
    with pytest.raises(ValidationError, match="text"):
        validate_message_template(None)
    with patch(
        "django_notification.models.notification_template.Template.substitute",
        side_effect=ValueError,
    ):
        with pytest.raises(ValidationError, match="Invalid notification template"):
            validate_message_template("$verb")
    with pytest.raises(ValidationError):
        NotificationTemplate(locale="en", subject="Title", body=" ").clean()


@pytest.mark.parametrize(
    "fields",
    [
        {"max_priority": "BAD"},
        {"min_priority": "URGENT", "max_priority": "LOW"},
        {"notification_status": "UNKNOWN"},
        {"action": "BAD"},
    ],
)
def test_routing_model_rejects_invalid_rules(fields):
    values = {"name": "Rule", "channels": ["email"], "action": "ADD", **fields}
    with pytest.raises(ValidationError):
        NotificationRoutingRule(**values).clean()


def test_routing_rejects_corrupt_persisted_values(user):
    notification = _delivery(user).notification
    with pytest.raises(ImproperlyConfigured, match="channel"):
        routed_channels(notification, ["fax"])
    notification.priority = "BAD"
    with pytest.raises(ImproperlyConfigured, match="priority"):
        routed_channels(notification, ["email"])
    notification.priority = "NORMAL"
    rule = NotificationRoutingRule.objects.create(
        name="Rule", channels=["email"], action="ADD"
    )
    for field, value, message in (
        ("max_priority", "BAD", "priority"),
        ("action", "BAD", "action"),
    ):
        NotificationRoutingRule.objects.filter(pk=rule.pk).update(**{field: value})
        with pytest.raises(ImproperlyConfigured, match=message):
            routed_channels(notification, ["email"])
        NotificationRoutingRule.objects.filter(pk=rule.pk).update(
            max_priority="URGENT", action="ADD"
        )


@pytest.mark.parametrize("zone", [None, "", "x" * 65])
def test_invalid_timezone_shape(zone):
    with pytest.raises(ValidationError):
        scheduling.valid_zone(zone)


def test_schedule_model_validates_boundaries():
    schedule = NotificationDeliverySchedule(channel="email", timezone="UTC")
    schedule.clean()
    schedule.quiet_start = time(23)
    with pytest.raises(ValidationError, match="Both"):
        schedule.clean()
    schedule.quiet_end = time(8)
    schedule.frequency = "DAILY"
    schedule.channel = "sms"
    with pytest.raises(ValidationError, match="email only"):
        schedule.clean()
    with pytest.raises(ValueError, match="does not request"):
        scheduling.next_digest_at(
            datetime.now(timezone.utc),
            SimpleNamespace(timezone="UTC", frequency="IMMEDIATE"),
        )


def test_spring_forward_quiet_end_normalizes_into_future():
    result = scheduling._wall_candidates(
        datetime(2026, 3, 8).date(), time(2, 30), ZoneInfo("America/New_York")
    )
    assert result == [datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc)]


def test_quiet_end_has_bounded_fallback_for_unusable_zone_candidates():
    now = datetime(2026, 1, 1, 23, tzinfo=timezone.utc)
    setting = SimpleNamespace(timezone="UTC", quiet_start=time(22), quiet_end=time(8))
    with patch.object(scheduling, "_wall_candidates", return_value=[now]) as candidates:
        result = scheduling.quiet_end_at(now, setting)
    assert candidates.call_count == 3
    assert result == datetime(2026, 1, 5, 8, tzinfo=timezone.utc)
