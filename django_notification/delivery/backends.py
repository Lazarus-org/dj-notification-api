"""Pluggable channel adapters; only Django email and static HTTPS are built in."""

import hashlib
import hmac
import ipaddress
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail

from .rendering import render_delivery


class DeliveryError(Exception):
    """Expected, sanitized backend failure (no confidential exception text)."""

    code = "delivery_error"
    permanent = False


class PermanentDeliveryError(DeliveryError):
    """Invalid destination or configuration; do not retry automatically."""

    code = "invalid_destination"
    permanent = True


class RetryableDeliveryError(DeliveryError):
    """Temporary delivery failure; retry with service-controlled backoff."""

    code = "temporary_failure"


class DeliveryBackend:
    """Implement send(delivery, *, idempotency_key) in application backends.

    Custom SMS/push backends may call delivery.rendering.render_delivery() to
    obtain the locale-specific subject/body, or retain provider-specific output.
    ``delivery.notification`` and ``delivery.recipient`` are model instances.
    A stable idempotency key can be passed to providers with dedupe support.
    Never log message contents, addresses, tokens or raw provider responses.

    """

    def send(self, delivery, *, idempotency_key):
        """Attempt delivery, raise DeliveryError on a known failure."""
        raise NotImplementedError

    def send_digest(self, digest, deliveries, *, idempotency_key):
        """Override to support digest mode; only email is built in."""
        raise PermanentDeliveryError("Digest delivery is unsupported")


class DjangoEmailBackend(DeliveryBackend):
    """Use Django's configured email backend; no extra dependencies."""

    def send_digest(self, digest, deliveries, *, idempotency_key):
        """Email a bounded digest; no message body is retained in the database."""
        if not deliveries or len(deliveries) > 50:
            raise PermanentDeliveryError("Digest batch size must be 1..50")
        recipient = deliveries[0].recipient
        if any(item.recipient_id != digest.recipient_id for item in deliveries):
            raise PermanentDeliveryError("Digest recipients are inconsistent")
        email = getattr(recipient, "email", None)
        if not isinstance(email, str) or not email.strip():
            raise PermanentDeliveryError("Recipient has no email")
        try:
            rendered = [render_delivery(item) for item in deliveries]
        except (ValidationError, ValueError) as exc:
            raise PermanentDeliveryError("Invalid digest template") from exc
        # Bound aggregate email size even when all individual templates are
        # configured at their maximum length.
        body = "\n\n---\n\n".join(
            f"{number}. {message.subject}\n{message.body}"
            for number, message in enumerate(rendered, 1)
        )
        subject = f"Notification digest ({len(rendered)} updates)"
        try:
            result = send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as exc:
            raise RetryableDeliveryError("Digest email backend failed") from exc
        if result != 1:
            raise RetryableDeliveryError("Digest email not accepted")

    def send(self, delivery, *, idempotency_key):
        """Send a plain-text message to the user's current email address."""
        email = getattr(delivery.recipient, "email", None)
        if not isinstance(email, str) or not email.strip():
            raise PermanentDeliveryError("Recipient has no email")
        try:
            rendered = render_delivery(delivery)
        except (ValidationError, ValueError) as exc:
            raise PermanentDeliveryError("Invalid delivery template") from exc
        # Ensure subjects cannot inject mail headers, whether from templates
        # or from legacy notification verbs.
        subject = " ".join(rendered.subject.split())[:127] or "Notification"
        message = rendered.body
        try:
            result = send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        except Exception as exc:
            raise RetryableDeliveryError("Email backend failed") from exc
        if result != 1:
            raise RetryableDeliveryError("Email backend did not accept message")


class _NoRedirect(HTTPRedirectHandler):
    """Do not forward signed delivery requests to arbitrary redirect hosts."""

    # Signature is imposed by urllib HTTPRedirectHandler.
    # pylint: disable-next=too-many-arguments
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Treat any redirect as an unsuccessful request."""
        return None


class SignedWebhookBackend(DeliveryBackend):
    """Send identifier-only JSON to an explicitly configured HTTPS endpoint.

    Only a trusted, operator-configured endpoint is supported. User- controlled
    notification links and data never determine the webhook destination. Deployments
    should also restrict outbound traffic at the network layer.

    """

    @staticmethod
    def _config():
        """Require TLS, static trusted host, and an HMAC signing secret."""
        url = getattr(settings, "DJANGO_NOTIFICATION_WEBHOOK_URL", None)
        secret = getattr(settings, "DJANGO_NOTIFICATION_WEBHOOK_SECRET", None)
        if not isinstance(url, str) or not isinstance(secret, str) or not secret:
            raise PermanentDeliveryError("Webhook configuration is missing")
        try:
            parts = urlsplit(url)
        except ValueError as exc:
            raise PermanentDeliveryError("Invalid webhook URL") from exc
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.fragment
        ):
            raise PermanentDeliveryError("Webhook URL must be trusted HTTPS")
        host = parts.hostname.lower()
        if host == "localhost" or host.endswith(".localhost"):
            raise PermanentDeliveryError("Local webhook endpoint not allowed")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            pass  # Hostname configured by the operator, not by the user.
        else:
            if not ip.is_global:
                raise PermanentDeliveryError("Non-public IP not allowed")
        return url, secret

    def send(self, delivery, *, idempotency_key):
        """POST signed JSON, never follow HTTP redirects."""
        url, secret = self._config()
        body = json.dumps(
            {
                "type": "notification.delivery",
                "delivery_id": delivery.pk,
                "notification_id": delivery.notification_id,
                "recipient_id": delivery.recipient_id,
                "channel": delivery.channel,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Notification-Signature": f"sha256={signature}",
                "Idempotency-Key": idempotency_key,
            },
        )
        try:
            response = build_opener(_NoRedirect()).open(req, timeout=10)
            with response:
                if not 200 <= response.status < 300:
                    raise RetryableDeliveryError("Webhook unsuccessful")
        except HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code not in (408, 429):
                raise PermanentDeliveryError("Webhook rejected request") from exc
            raise RetryableDeliveryError("Webhook transport failed") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise RetryableDeliveryError("Webhook transport failed") from exc
