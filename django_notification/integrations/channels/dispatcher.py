"""Explicit, best-effort bridge from post-commit events to Channels groups.

No Channels imports happen until registration or dispatch is requested.

"""

import logging

from django.conf import settings
from django.utils.crypto import salted_hmac

from django_notification.events import NotificationEventKind, notification_event
from django_notification.integrations.channels.audience import eligible_audience

logger = logging.getLogger(__name__)
_DISPATCH_UID = "django_notification.channels.optional_dispatcher.v1"
_CONTENT_EVENTS = frozenset(
    (
        NotificationEventKind.CREATED,
        NotificationEventKind.UPDATED,
        NotificationEventKind.SENT,
    )
)
_PERSONAL_EVENTS = frozenset(
    (
        NotificationEventKind.SEEN,
        NotificationEventKind.UNSEEN,
        NotificationEventKind.CLEARED,
    )
)


def configured_database():
    """Do not mix event audiences across database aliases."""
    return getattr(settings, "DJANGO_NOTIFICATION_CHANNELS_DATABASE_ALIAS", "default")


def user_channel_group(user_id, database=None):
    """Opaque, ASCII-safe Channels group for all sockets of one user."""
    database = configured_database() if database is None else database
    digest = salted_hmac(
        "django_notification.channels.user.v1",
        f"{database}:{user_id}",
        algorithm="sha1",
    ).hexdigest()
    return f"djnotify.user.{digest}"


def _channel_layer():
    from channels.layers import get_channel_layer

    return get_channel_layer()


def _send(layer, user_id, event):
    """Send only safe event metadata, never notification or recipient contents."""
    from asgiref.sync import async_to_sync

    async_to_sync(layer.group_send)(
        user_channel_group(user_id, event.database),
        {
            "type": "notification.push",
            "kind": event.kind,
            "notification_id": event.notification_id,
            "affected_count": event.affected_count,
            "batch": event.batch,
        },
    )


def _handle_event(sender, event, **kwargs):
    """Process committed events; unsupported aggregate kinds need REST polling."""
    if event.database != configured_database():
        return
    if event.kind not in _CONTENT_EVENTS | _PERSONAL_EVENTS:
        return
    # An aggregate send has no notification IDs, so its recipient set cannot
    # be recovered safely; never broadcast it to every connected client.
    if event.kind in _CONTENT_EVENTS and event.notification_id is None:
        return
    # Unsent creation/update events must not cause a notification delivery.
    if event.kind == NotificationEventKind.CREATED and not event.is_sent:
        return

    def send_to_layer():
        """Propagate failures in durable mode for a retryable outbox claim."""
        layer = _channel_layer()
        if layer is None:
            raise RuntimeError("Notification Channels layer unavailable")
        if event.kind in _PERSONAL_EVENTS:
            if event.user_id is not None:
                _send(layer, event.user_id, event)
        else:
            for recipient_id in eligible_audience(
                event.notification_id, event.database
            ):
                _send(layer, recipient_id, event)

    if (
        getattr(settings, "DJANGO_NOTIFICATION_API_EVENT_DELIVERY", "signal")
        == "outbox"
    ):
        # At-least-once: a partial fan-out followed by an error can replay to
        # earlier recipients. Clients must tolerate duplicate invalidations.
        send_to_layer()
    else:
        try:
            send_to_layer()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.error("Notification Channels dispatch failed")


def connect_notification_channels():
    """Explicitly install the adapter once from a host application's ready().

    Raises a clear error if Channels has not been installed. With no call to this
    function, the entire package remains Channels- independent.

    """
    try:
        from channels.layers import get_channel_layer
    except ImportError as exc:
        raise RuntimeError("Install Django Channels to enable this adapter") from exc
    layer = get_channel_layer()
    if layer is None or not all(
        hasattr(layer, method)
        for method in ("group_add", "group_discard", "group_send")
    ):
        raise RuntimeError("Configure a Channels group-capable channel layer")
    notification_event.connect(_handle_event, dispatch_uid=_DISPATCH_UID, weak=False)


def disconnect_notification_channels():
    """Unregister the adapter (especially useful in isolated tests)."""
    notification_event.disconnect(dispatch_uid=_DISPATCH_UID)
