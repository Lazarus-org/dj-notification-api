"""Opt-in event receiver and configured per-channel delivery backend loading."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from django_notification.events import NotificationEventKind, notification_event

from .backends import DeliveryBackend

CHANNELS = frozenset(("email", "sms", "push", "webhook"))
_DISPATCH_UID = "django_notification.delivery.event_fanout.v1"


def backend_paths():
    """Return configured channels; nothing is enabled by default."""
    mapping = getattr(settings, "DJANGO_NOTIFICATION_DELIVERY_BACKENDS", {})
    if not isinstance(mapping, dict):
        raise ImproperlyConfigured("DELIVERY_BACKENDS must be a dictionary")
    for channel, path in mapping.items():
        if channel not in CHANNELS or not isinstance(path, str) or not path:
            raise ImproperlyConfigured("Invalid delivery backend channel or path")
    return mapping


def load_backend(channel):
    """Import and validate an application-defined delivery adapter."""
    mapping = backend_paths()
    if channel not in mapping:
        raise ImproperlyConfigured("Delivery channel is not enabled")
    try:
        cls = import_string(mapping[channel])
    except (ImportError, AttributeError, ValueError) as exc:
        raise ImproperlyConfigured("Delivery backend import failed") from exc
    if not isinstance(cls, type) or not issubclass(cls, DeliveryBackend):
        raise ImproperlyConfigured("Delivery backend must extend DeliveryBackend")
    try:
        backend = cls()
    except Exception as exc:
        raise ImproperlyConfigured("Delivery backend construction failed") from exc
    from .backends import DeliveryError, SignedWebhookBackend

    if isinstance(backend, SignedWebhookBackend):
        try:
            backend._config()
        except (DeliveryError, ValueError) as exc:
            raise ImproperlyConfigured("Webhook configuration is invalid") from exc
    return backend


def _handle_event(sender, event, **kwargs):
    """Create durable jobs only when content becomes sent/available."""
    if (
        event.kind not in (NotificationEventKind.CREATED, NotificationEventKind.SENT)
        or not event.is_sent
        or event.notification_id is None
    ):
        return
    from .service import enqueue_notification_deliveries

    enqueue_notification_deliveries(event.notification_id, event.database)


def connect_notification_delivery():
    """Register a durable sink in *every* outbox-worker process."""
    if (
        getattr(settings, "DJANGO_NOTIFICATION_API_EVENT_DELIVERY", "signal")
        != "outbox"
    ):
        raise ImproperlyConfigured("External delivery requires outbox mode")
    paths = backend_paths()
    if not paths:
        raise ImproperlyConfigured("Configure at least one delivery backend")
    for channel in paths:
        load_backend(channel)  # Fail fast on invalid paths.
    notification_event.connect(
        _handle_event,
        dispatch_uid=_DISPATCH_UID,
        weak=False,
    )


def disconnect_notification_delivery():
    """Remove the receiver for test isolation."""
    notification_event.disconnect(dispatch_uid=_DISPATCH_UID)
