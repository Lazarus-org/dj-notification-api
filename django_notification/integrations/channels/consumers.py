"""Authenticated, read-only notification event WebSocket consumer.

Importing this module requires Django Channels. Core Django notification functionality
does not import it unless an ASGI application opts in.

"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from django_notification.integrations.channels.audience import (
    active_user,
    notification_visible,
)
from django_notification.integrations.channels.dispatcher import (
    _CONTENT_EVENTS,
    _PERSONAL_EVENTS,
    configured_database,
    user_channel_group,
)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Listen for safe invalidation hints addressed to the authenticated user.

    Clients always fetch notification content via the authorized REST API. No client-
    supplied subscription or state-changing commands are accepted.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.joined_group = None
        self.user_id = None
        self.database = None

    async def connect(self):
        self.joined_group = None
        user = self.scope.get("user")
        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or getattr(user, "pk", None) is None
        ):
            await self.close(code=4401)
            return
        self.user_id = user.pk
        self.database = configured_database()
        valid = await database_sync_to_async(active_user)(self.user_id, self.database)
        if valid is None:
            await self.close(code=4403)
            return
        if self.channel_layer is None:
            await self.close(code=1011)
            return
        group = user_channel_group(self.user_id, self.database)
        await self.channel_layer.group_add(group, self.channel_name)
        self.joined_group = group
        await self.accept()

    async def disconnect(self, code):
        if self.joined_group is not None and self.channel_layer is not None:
            await self.channel_layer.group_discard(self.joined_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Reject client messages: this socket is server-to-client only."""
        await self.close(code=4400)

    async def notification_push(self, event):
        """Recheck current authorization before forwarding a queued event."""
        if self.joined_group is None:
            return
        notification_id = event.get("notification_id")
        if event.get("kind") not in _CONTENT_EVENTS | _PERSONAL_EVENTS:
            return
        if event["kind"] in _CONTENT_EVENTS:
            if notification_id is None:
                return
            active, allowed = await database_sync_to_async(notification_visible)(
                self.user_id, notification_id, self.database
            )
        else:
            active = (
                await database_sync_to_async(active_user)(self.user_id, self.database)
                is not None
            )
            allowed = True
        if not active:
            await self.close(code=4403)
            return
        if not allowed:
            return
        await self.send_json(
            {
                "type": "notification.event",
                "event": event["kind"],
                "notification_id": notification_id,
                "batch": event["batch"],
                "affected_count": event["affected_count"],
            }
        )
