"""Phase 15: channel preferences and restricted localized template delivery."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.delivery.backends import DjangoEmailBackend
from django_notification.delivery.preferences import channel_enabled
from django_notification.delivery.rendering import render_delivery
from django_notification.delivery.service import (
    NotificationDeliveryService,
    enqueue_notification_deliveries,
)
from django_notification.models import (
    Notification,
    NotificationCategory,
    NotificationChannelPreference,
    NotificationDelivery,
    NotificationTemplate,
)
from django_notification.models.notification_delivery import DeliveryStatus
from django_notification.models.notification_template import (
    validate_message_template,
)

pytestmark = pytest.mark.django_db

BACKENDS = {
    "email": "django_notification.delivery.backends.DjangoEmailBackend",
    "sms": "django_notification.delivery.backends.DjangoEmailBackend",
}


def _category(slug="updates", mandatory=False):
    return NotificationCategory.objects.create(
        slug=slug,
        name="Updates",
        is_mandatory=mandatory,
    )


def _notify(user, category="general"):
    return Notification.objects.create_notification(
        actor=user,
        verb="Build ready",
        description="A report is available",
        recipients=[user],
        category=category,
        is_sent=True,
        link="https://example.org/report",
    )


def _delivery(user, category="general", channel="email"):
    notification = _notify(user, category)
    return NotificationDelivery.objects.create(
        notification=notification,
        recipient=user,
        channel=channel,
    )


def _url(slug, channel):
    return reverse(
        "notifications-set-channel-preference",
        kwargs={
            "category_slug": slug,
            "channel": channel,
        },
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_template_rejects_arbitrary_expression_and_unknown_variables():
    """Only a small allowlisted substitution language is supported."""
    for value in ("$recipient.email", "$password", "${__class__}", "$!", "${bad}"):
        with pytest.raises(ValidationError):
            validate_message_template(value)
    validate_message_template("$$$verb: ${description} $link")


def test_model_rejects_bad_locale_and_unknown_placeholder():
    """Admin validation rejects malformed tags and unsafe templates."""
    category = _category()
    template = NotificationTemplate(
        category=category,
        channel="email",
        locale="xx_@@",
        subject="Title",
        body="$verb",
    )
    with pytest.raises(ValidationError):
        template.full_clean()
    template.locale = "en"
    template.body = "$user_id"
    with pytest.raises(ValidationError):
        template.full_clean()


@override_settings(DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE="en")
def test_locale_template_exact_and_default_fallback(user):
    """Select per-recipient locale, then deployment fallback without N+1."""
    category = _category()
    NotificationTemplate.objects.create(
        category=category,
        channel="email",
        locale="en",
        subject="Ready $priority",
        body="${description}: $link",
    )
    delivery = _delivery(user, category.pk)
    message = render_delivery(delivery)
    assert message.subject == "Ready NORMAL"
    assert message.body == "A report is available: https://example.org/report"
    assert message.locale == "en"
    NotificationTemplate.objects.create(
        category=category,
        channel="email",
        locale="fa",
        subject="Notice",
        body="FA: $verb",
    )
    with patch(
        "django_notification.delivery.rendering.delivery_locale", return_value="fa-ir"
    ):
        assert render_delivery(delivery).body == "FA: Build ready"


@override_settings(DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE="en")
def test_missing_template_preserves_existing_email_payload(user):
    """Unconfigured templates do not alter Phase-14 email behavior."""
    delivery = _delivery(user)
    with patch(
        "django_notification.delivery.backends.send_mail", return_value=1
    ) as mail:
        DjangoEmailBackend().send(delivery, idempotency_key="send-1")
    args = mail.call_args.args
    assert args[0] == "Build ready"
    assert "A report is available" in args[1]
    assert "https://example.org/report" in args[1]


@override_settings(DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE="en")
def test_email_backend_uses_managed_template(user):
    """Built-in email adapter sends rendered content, not raw notification verb."""
    category = _category()
    NotificationTemplate.objects.create(
        category=category,
        channel="email",
        locale="en",
        subject="Report: $verb",
        body="${description}",
    )
    delivery = _delivery(user, category.pk)
    with patch(
        "django_notification.delivery.backends.send_mail", return_value=1
    ) as mail:
        DjangoEmailBackend().send(delivery, idempotency_key="send-2")
    assert mail.call_args.args[:2] == ("Report: Build ready", "A report is available")


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_channel_opt_out_skips_only_selected_external_channel(user):
    """Opting out of email leaves SMS and the personal inbox intact."""
    category = _category()
    NotificationChannelPreference.objects.create(
        user=user,
        category=category,
        channel="email",
        enabled=False,
    )
    notification = _notify(user, category.pk)
    assert enqueue_notification_deliveries(notification.pk) == 1
    assert list(NotificationDelivery.objects.values_list("channel", flat=True)) == [
        "sms"
    ]
    assert Notification.objects.visible_to(user).filter(pk=notification.pk).exists()


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_mandatory_category_bypasses_stale_disable_record(user):
    """Mandatory category policy wins over legacy disabled override rows."""
    category = _category(mandatory=True)
    NotificationChannelPreference.objects.create(
        user=user,
        category=category,
        channel="email",
        enabled=False,
    )
    notification = _notify(user, category.pk)
    assert enqueue_notification_deliveries(notification.pk) == 2
    assert channel_enabled(user.pk, category.pk, "email")


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_preference_change_cancels_queued_delivery(user):
    """Worker checks current preferences before calling external providers."""
    category = _category()
    notification = _notify(user, category.pk)
    enqueue_notification_deliveries(notification.pk)
    NotificationChannelPreference.objects.create(
        user=user,
        category=category,
        channel="email",
        enabled=False,
    )
    with patch(
        "django_notification.delivery.backends.send_mail", return_value=1
    ) as mail:
        assert NotificationDeliveryService().process_next() == "cancelled"
    mail.assert_not_called()
    assert NotificationDelivery.objects.get(channel="email").status == (
        DeliveryStatus.CANCELLED
    )


def test_self_service_channel_preference_is_user_scoped(user, another_user):
    """A user cannot change somebody else's notification channel settings."""
    category = _category()
    response = _client(user).patch(
        _url(category.pk, "email"),
        {
            "enabled": False,
        },
        format="json",
    )
    assert response.status_code == 200
    assert NotificationChannelPreference.objects.filter(
        user=user,
        category=category,
        channel="email",
        enabled=False,
    ).exists()
    assert not NotificationChannelPreference.objects.filter(
        user=another_user,
        category=category,
    ).exists()
    response = _client(user).patch(
        _url(category.pk, "email"),
        {
            "enabled": True,
        },
        format="json",
    )
    assert response.status_code == 200
    assert not NotificationChannelPreference.objects.filter(
        user=user,
        category=category,
    ).exists()


def test_mandatory_channel_disable_rejected(user):
    """Mandatory categories cannot be disabled via user-channel API."""
    category = _category(mandatory=True)
    response = _client(user).patch(
        _url(category.pk, "sms"),
        {
            "enabled": False,
        },
        format="json",
    )
    assert response.status_code == 400
    assert NotificationChannelPreference.objects.count() == 0


def test_channel_preference_rejects_unknown_channel(user):
    """Unknown channels are rejected without creating a policy row."""
    category = _category()
    response = _client(user).patch(
        _url(category.pk, "fax"),
        {
            "enabled": False,
        },
        format="json",
    )
    assert response.status_code == 404


def test_effective_preferences_read_only_authentication(user, another_user):
    """The preference list includes only the current user's effective state."""
    category = _category()
    NotificationChannelPreference.objects.create(
        user=another_user,
        category=category,
        channel="email",
        enabled=False,
    )
    response = _client(user).get(reverse("notifications-channel-preferences"))
    assert response.status_code == 200
    values = [v for v in response.data if v["category"] == category.pk]
    assert next(v for v in values if v["channel"] == "email")["enabled"]


@override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=BACKENDS)
def test_group_member_channel_opt_out_is_independent(user, another_user):
    """Only the opting-out group member loses that external channel."""
    from django.contrib.auth.models import Group

    group = Group.objects.create(name="Template-alert-subscribers")
    group.user_set.add(user, another_user)
    category = _category()
    NotificationChannelPreference.objects.create(
        user=user,
        category=category,
        channel="sms",
        enabled=False,
    )
    notification = Notification.objects.create_notification(
        actor=user,
        verb="Group message",
        groups=[group],
        category=category.pk,
        is_sent=True,
    )
    assert enqueue_notification_deliveries(notification.pk) == 3
    channels = {
        (r.recipient_id, r.channel)
        for r in NotificationDelivery.objects.filter(notification=notification)
    }
    assert channels == {
        (user.pk, "email"),
        (another_user.pk, "email"),
        (another_user.pk, "sms"),
    }
