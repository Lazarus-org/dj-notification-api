"""Exercise destination validation, signatures, redirects and SMTP boundaries."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from django_notification.delivery.backends import (
    DjangoEmailBackend,
    PermanentDeliveryError,
    RetryableDeliveryError,
    SignedWebhookBackend,
    _NoRedirect,
)
from django_notification.settings.conf import NotificationConfig


@pytest.fixture
def webhook_settings(settings):
    settings.DJANGO_NOTIFICATION_WEBHOOK_URL = "https://hooks.example.com/events"
    settings.DJANGO_NOTIFICATION_WEBHOOK_SECRET = "test-signing-key"
    return settings


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://localhost",
        "https://sub.localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://10.0.0.1",
        "https://user:password@example.com",
        "https://example.com/#private",
        "https://[broken",
        "https:///missing-host",
    ],
)
def test_webhook_rejects_unsafe_static_destinations(webhook_settings, url):
    webhook_settings.DJANGO_NOTIFICATION_WEBHOOK_URL = url
    with pytest.raises(PermanentDeliveryError):
        SignedWebhookBackend._config()


def test_webhook_signature_covers_exact_metadata_and_never_content(webhook_settings):
    delivery = SimpleNamespace(
        pk=7, notification_id=11, recipient_id=13, channel="webhook"
    )
    response = MagicMock(status=204)
    with patch("django_notification.delivery.backends.build_opener") as opener:
        opener.return_value.open.return_value = response
        SignedWebhookBackend().send(delivery, idempotency_key="delivery:7")
    request = opener.return_value.open.call_args.args[0]
    expected = hmac.new(b"test-signing-key", request.data, hashlib.sha256).hexdigest()
    assert request.get_header("X-notification-signature") == f"sha256={expected}"
    assert request.get_header("Idempotency-key") == "delivery:7"
    assert json.loads(request.data) == {
        "type": "notification.delivery",
        "delivery_id": 7,
        "notification_id": 11,
        "recipient_id": 13,
        "channel": "webhook",
    }
    assert opener.return_value.open.call_args.kwargs == {"timeout": 10}
    assert (
        _NoRedirect().redirect_request(
            None, None, 302, None, None, "https://evil.example"
        )
        is None
    )


@pytest.mark.parametrize(
    "code,expected",
    [
        (302, RetryableDeliveryError),
        (400, PermanentDeliveryError),
        (408, RetryableDeliveryError),
        (429, RetryableDeliveryError),
        (503, RetryableDeliveryError),
    ],
)
def test_webhook_http_errors_are_classified_without_response_leaks(
    webhook_settings, code, expected
):
    delivery = SimpleNamespace(
        pk=1, notification_id=2, recipient_id=3, channel="webhook"
    )
    error = HTTPError("https://hooks.example.com", code, "PRIVATE", {}, None)
    with patch("django_notification.delivery.backends.build_opener") as opener:
        opener.return_value.open.side_effect = error
        with pytest.raises(expected) as caught:
            SignedWebhookBackend().send(delivery, idempotency_key="test")
    assert "PRIVATE" not in str(caught.value)


def test_webhook_transport_error_is_retryable(webhook_settings):
    delivery = SimpleNamespace(
        pk=1, notification_id=2, recipient_id=3, channel="webhook"
    )
    with patch("django_notification.delivery.backends.build_opener") as opener:
        opener.return_value.open.side_effect = URLError("PRIVATE")
        with pytest.raises(RetryableDeliveryError):
            SignedWebhookBackend().send(delivery, idempotency_key="test")


@pytest.mark.django_db
def test_email_uses_only_current_recipient_and_safe_subject(user, mailoutbox):
    from django_notification.models import Notification, NotificationDelivery

    item = Notification.objects.create_notification(
        actor=user,
        verb="Title\r\nBcc: other@example.com",
        recipients=[user],
        is_sent=True,
    )
    job = NotificationDelivery.objects.create(
        notification=item, recipient=user, channel="email"
    )
    DjangoEmailBackend().send(job, idempotency_key="email:1")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [user.email]
    assert mailoutbox[0].bcc == []
    assert "\r" not in mailoutbox[0].subject and "\n" not in mailoutbox[0].subject
    user.email = ""
    with pytest.raises(PermanentDeliveryError):
        DjangoEmailBackend().send(job, idempotency_key="email:1")


@pytest.mark.parametrize(
    "path", ["django.contrib.admin.sites.AdminSite", "django.contrib.admin.site"]
)
def test_custom_admin_site_resolves_to_instance(settings, path):
    from django.contrib.admin.sites import AdminSite

    settings.DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = path
    assert isinstance(NotificationConfig().admin_site_class, AdminSite)


def test_custom_admin_site_rejects_unrelated_class(settings):
    from django.core.exceptions import ImproperlyConfigured

    settings.DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = "django.http.HttpRequest"
    with pytest.raises(ImproperlyConfigured):
        NotificationConfig()
