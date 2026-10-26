"""Optional end-to-end Channels smoke tests, deferred to final runtime gate."""

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser

pytest.importorskip("channels")

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from django_notification.integrations.channels.consumers import NotificationConsumer
from django_notification.integrations.channels.dispatcher import user_channel_group
from django_notification.models import Notification

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _layer(settings):
    """In-memory layer is sufficient for a single-process contract test."""
    settings.CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


def _app_with_user(user):
    """Inject an authenticated identity as host AuthMiddlewareStack would."""
    inner = NotificationConsumer.as_asgi()

    async def app(scope, receive, send):
        scope["user"] = user
        return await inner(scope, receive, send)

    return app


def test_socket_rejects_anonymous_identity():
    """No query-string identity or unauthenticated subscriptions are allowed."""

    async def exercise():
        ws = WebsocketCommunicator(
            _app_with_user(AnonymousUser()), "/ws/notifications/"
        )
        connected, code = await ws.connect()
        assert not connected
        assert code == 4401
        await ws.wait()

    async_to_sync(exercise)()


def test_real_session_cookie_authentication_stack(user, settings):
    """Resolve a real Django session through the host authentication stack."""
    from channels.auth import AuthMiddlewareStack
    from django.test import Client

    client = Client()
    client.force_login(user)
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    async def exercise():
        ws = WebsocketCommunicator(
            AuthMiddlewareStack(NotificationConsumer.as_asgi()),
            "/ws/notifications/",
            headers=[
                (b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode("ascii"))
            ],
        )
        connected, _ = await ws.connect()
        assert connected
        await ws.disconnect()

        anonymous = WebsocketCommunicator(
            AuthMiddlewareStack(NotificationConsumer.as_asgi()),
            "/ws/notifications/",
            headers=[
                (
                    b"cookie",
                    f"{settings.SESSION_COOKIE_NAME}=invalid-session".encode("ascii"),
                )
            ],
        )
        connected, code = await anonymous.connect()
        assert not connected and code == 4401
        await anonymous.wait()

    async_to_sync(exercise)()


def test_authenticated_socket_receives_only_metadata(user):
    """Client gets a re-authorized hint, not private notification contents."""
    item = Notification.objects.create_notification(
        actor=user, verb="Private", recipients=[user], is_sent=True
    )

    async def exercise():
        ws = WebsocketCommunicator(_app_with_user(user), "/ws/notifications/")
        connected, _ = await ws.connect()
        assert connected
        await get_channel_layer().group_send(
            user_channel_group(user.pk),
            {
                "type": "notification.push",
                "kind": "notification.created",
                "notification_id": item.pk,
                "batch": False,
                "affected_count": 1,
            },
        )
        payload = await ws.receive_json_from(timeout=3)
        assert payload == {
            "type": "notification.event",
            "event": "notification.created",
            "notification_id": item.pk,
            "batch": False,
            "affected_count": 1,
        }
        await ws.disconnect()

    async_to_sync(exercise)()


def test_inactive_user_cannot_connect(user):
    """An expired/deactivated Django account cannot receive WebSocket data."""
    user.is_active = False
    user.save(update_fields=["is_active"])

    async def exercise():
        ws = WebsocketCommunicator(_app_with_user(user), "/ws/notifications/")
        connected, code = await ws.connect()
        assert not connected
        assert code == 4403
        await ws.wait()

    async_to_sync(exercise)()
