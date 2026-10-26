"""Optional Channels dispatcher event and recipient isolation tests."""

from unittest.mock import patch

import pytest

from django_notification.events import NotificationEvent, NotificationEventKind
from django_notification.integrations.channels.dispatcher import (
    _handle_event,
    connect_notification_channels,
    disconnect_notification_channels,
)
from django_notification.models import Notification

pytest.importorskip("channels")

pytestmark = pytest.mark.django_db


def test_group_fanout_is_only_for_authorized_users(user, another_user, group):
    """No broadcast to unrelated staff or arbitrary connected sockets."""
    user.groups.add(group)
    item = Notification.objects.create_notification(
        actor=user, verb="Group", groups=[group], is_sent=True
    )
    event = NotificationEvent(
        kind=NotificationEventKind.CREATED,
        database="default",
        notification_id=item.pk,
        is_sent=True,
    )
    layer = object()
    with (
        patch(
            "django_notification.integrations.channels.dispatcher._channel_layer",
            return_value=layer,
        ),
        patch("django_notification.integrations.channels.dispatcher._send") as send,
    ):
        _handle_event(Notification, event)
    send.assert_called_once_with(layer, user.pk, event)


def test_personal_state_event_is_addressed_only_to_its_owner(user):
    """A seen event cannot expose another recipient's read state."""
    event = NotificationEvent(
        kind=NotificationEventKind.SEEN,
        database="default",
        user_id=user.pk,
        notification_id=123,
    )
    layer = object()
    with (
        patch(
            "django_notification.integrations.channels.dispatcher._channel_layer",
            return_value=layer,
        ),
        patch("django_notification.integrations.channels.dispatcher._send") as send,
    ):
        _handle_event(Notification, event)
    send.assert_called_once_with(layer, user.pk, event)


def test_unsent_and_unscoped_bulk_events_do_not_fan_out():
    """Drafts and unidentified aggregate sends are not safe to broadcast."""
    events = (
        NotificationEvent(
            NotificationEventKind.CREATED,
            "default",
            notification_id=1,
            is_sent=False,
        ),
        NotificationEvent(
            NotificationEventKind.SENT,
            "default",
            notification_id=None,
            batch=True,
        ),
        NotificationEvent(
            NotificationEventKind.HARD_DELETED,
            "default",
            notification_id=1,
        ),
    )
    with patch(
        "django_notification.integrations.channels.dispatcher._channel_layer"
    ) as layer:
        for event in events:
            _handle_event(Notification, event)
    layer.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("layer", ["channels.layers.InMemoryChannelLayer"])
def test_explicit_registration_is_idempotent(settings, layer):
    """Host app may initialize twice without registering duplicate listeners."""
    from django_notification.events import notification_event

    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": layer},
    }

    try:
        connect_notification_channels()
        count = len(notification_event.receivers)
        connect_notification_channels()
        assert len(notification_event.receivers) == count
    finally:
        disconnect_notification_channels()
