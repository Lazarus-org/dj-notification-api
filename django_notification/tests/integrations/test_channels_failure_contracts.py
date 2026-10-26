"""Optional Channels authorization and transport failure contracts."""

import builtins
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.test import override_settings

pytest.importorskip("channels")

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from django_notification.events import NotificationEvent
from django_notification.integrations.channels import dispatcher
from django_notification.integrations.channels.consumers import NotificationConsumer
from django_notification.integrations.channels.routing import (
    notification_websocket_urlpatterns,
)
from django_notification.models import Notification
from django_notification.tests.integrations.test_channels_consumer import _app_with_user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def layer(settings):
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


def test_routing_exports_notification_socket():
    assert len(notification_websocket_urlpatterns) == 1
    assert (
        notification_websocket_urlpatterns[0].resolve("ws/notifications/") is not None
    )


def test_dispatch_uses_real_layer_and_safe_metadata(user):
    event = NotificationEvent(
        "notification.seen", "default", user_id=user.pk, batch=True
    )
    layer = dispatcher._channel_layer()
    channel = async_to_sync(layer.new_channel)()
    group = dispatcher.user_channel_group(user.pk)
    async_to_sync(layer.group_add)(group, channel)
    dispatcher._handle_event(Notification, event)
    message = async_to_sync(layer.receive)(channel)
    assert message == {
        "type": "notification.push",
        "kind": event.kind,
        "notification_id": None,
        "affected_count": 1,
        "batch": True,
    }


def test_dispatch_failure_is_redacted_in_signal_mode_and_propagates_in_outbox(caplog):
    event = NotificationEvent("notification.seen", "default", user_id=1)
    with patch.object(dispatcher, "_channel_layer", return_value=None):
        dispatcher._handle_event(Notification, event)
        assert "dispatch failed" in caplog.text
        with override_settings(DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox"):
            with pytest.raises(RuntimeError, match="unavailable"):
                dispatcher._handle_event(Notification, event)
    with patch.object(dispatcher, "_channel_layer") as get_layer:
        dispatcher._handle_event(
            Notification, NotificationEvent("notification.seen", "other", user_id=1)
        )
        get_layer.assert_not_called()


def test_registration_requires_optional_dependency_and_group_capable_layer():
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "channels.layers":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=importing):
        with pytest.raises(RuntimeError, match="Install Django Channels"):
            dispatcher.connect_notification_channels()
    with patch("channels.layers.get_channel_layer", return_value=object()):
        with pytest.raises(RuntimeError, match="group-capable"):
            dispatcher.connect_notification_channels()


def test_socket_without_layer_closes_with_server_error(user, settings):
    settings.CHANNEL_LAYERS = {}

    async def exercise():
        ws = WebsocketCommunicator(_app_with_user(user), "/ws/notifications/")
        assert await ws.connect() == (False, 1011)
        await ws.wait()

    async_to_sync(exercise)()


def test_socket_rejects_client_commands(user):
    async def exercise():
        ws = WebsocketCommunicator(_app_with_user(user), "/ws/notifications/")
        assert (await ws.connect())[0]
        await ws.send_json_to({"subscribe": "someone-else"})
        assert await ws.receive_output() == {"type": "websocket.close", "code": 4400}
        await ws.disconnect()

    async_to_sync(exercise)()


def test_consumer_drops_unknown_unscoped_and_revoked_messages(user):
    notification = Notification.objects.create_notification(
        "Private", user, recipients=[user], is_sent=True
    )
    notification.recipient.clear()

    async def exercise():
        consumer = NotificationConsumer()
        consumer.send_json = AsyncMock()
        consumer.close = AsyncMock()
        consumer.joined_group = None
        event = {
            "kind": "notification.created",
            "notification_id": notification.pk,
            "batch": False,
            "affected_count": 1,
        }
        await consumer.notification_push(event)
        consumer.joined_group = "joined"
        consumer.user_id = user.pk
        consumer.database = "default"
        await consumer.notification_push({**event, "kind": "unknown"})
        await consumer.notification_push({**event, "notification_id": None})
        await consumer.notification_push(event)
        consumer.send_json.assert_not_awaited()
        consumer.close.assert_not_awaited()
        await consumer.notification_push({**event, "kind": "notification.seen"})
        consumer.send_json.assert_awaited_once()

    async_to_sync(exercise)()


@pytest.mark.parametrize("kind", ["notification.created", "notification.seen"])
def test_connected_identity_is_rechecked_before_every_message(user, kind):
    async def exercise():
        ws = WebsocketCommunicator(_app_with_user(user), "/ws/notifications/")
        assert (await ws.connect())[0]
        from channels.db import database_sync_to_async

        await database_sync_to_async(type(user).objects.filter(pk=user.pk).update)(
            is_active=False
        )
        await get_channel_layer().group_send(
            dispatcher.user_channel_group(user.pk),
            {
                "type": "notification.push",
                "kind": kind,
                "notification_id": 1,
                "batch": False,
                "affected_count": 1,
            },
        )
        assert await ws.receive_output() == {"type": "websocket.close", "code": 4403}
        await ws.disconnect()

    async_to_sync(exercise)()
