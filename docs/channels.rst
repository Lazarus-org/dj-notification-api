Optional Django Channels integration
====================================

This opt-in adapter sends **notification invalidation hints**, not serialized
notification contents. Install Django Channels only in projects that need
WebSockets; plain ``dj-notification-api`` continues to run without Channels,
Redis, Daphne, or a channel layer.

Installation
------------

Install Channels and an ASGI server in your host project::

    pip install 'dj-notification-api[channels]' 'daphne>=4,<5'

For multi-process/multi-server deployments, also install and configure the
production Redis channel layer::

    pip install 'dj-notification-api[redis]'

The in-memory layer is suitable **only for single-process development or
testing**, not multi-worker production. A channel-layer backend supporting
``group_add``, ``group_discard`` and ``group_send`` is required.

Explicit event registration
---------------------------

Connect the adapter once from **your host application** ``AppConfig.ready()``::

    from django.apps import AppConfig

    class YourAppConfig(AppConfig):
        name = "your_app"

        def ready(self):
            from django_notification.integrations.channels import (
                connect_notification_channels,
            )
            connect_notification_channels()

Registration is idempotent. The package **does not register this adapter**
implicitly: installing Channels does not alter the behavior of applications
that do not opt in. Calling the register function without Channels or a
usable channel layer raises a clear configuration error.

ASGI configuration
------------------

In your host project's ``asgi.py`` (after setting ``DJANGO_SETTINGS_MODULE``)::

    from django.core.asgi import get_asgi_application

    django_asgi_app = get_asgi_application()

    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator
    from django_notification.integrations.channels.routing import (
        notification_websocket_urlpatterns,
    )

    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(notification_websocket_urlpatterns))
        ),
    })

The route is ``ws/notifications/``. It uses Django session authentication
via ``AuthMiddlewareStack``. Token/JWT users must implement their own secure
ASGI authentication middleware, which populates ``scope['user']``; passing an
arbitrary ``user_id`` through query parameters is **not supported**. Protect
cookie-authenticated WebSockets with a trusted origin validator (and proper
``ALLOWED_HOSTS``). Use WSS in production.

Connect with the currently authenticated user's Django session. Multiple
sockets for one user receive independent copies of the same hint. Clients
cannot subscribe to other accounts, request arbitrary group subscriptions,
or mutate notification state over the socket. All writes use the REST API.

Payload and consumption
-----------------------

Example server-to-client JSON::

    {
        "type": "notification.event",
        "event": "notification.created",
        "notification_id": 91,
        "batch": false,
        "affected_count": 1
    }

Use the event as a **hint** to refresh the authenticated user's inbox or
summary using the REST API. No message body, category, group identifier,
email, title, recipient list, or actor metadata is sent over WebSockets.
A ``notification_id`` may be ``null`` for user-scoped bulk read/clear events.
``affected_count`` is not a guaranteed count of newly persisted changes
under concurrency.

Refresh from a browser client
-----------------------------

For a same-origin, session-authenticated application, connect without sending
subscription commands. This example dispatches a local browser event after
fetching the summary; your UI can listen for notification-summary and update
its badge. Adjust the REST prefix if you mounted it differently.

.. code-block:: javascript

    let retryDelay = 1000;

    async function refreshSummary() {
      const response = await fetch("/notification/notifications/summary/", {
        credentials: "same-origin",
      });
      if (!response.ok) return;
      const summary = await response.json();
      window.dispatchEvent(new CustomEvent("notification-summary", {
        detail: summary,
      }));
    }

    function connectNotifications() {
      const scheme = location.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(`${scheme}//${location.host}/ws/notifications/`);
      socket.onopen = () => {
        retryDelay = 1000;
        refreshSummary(); // Reconcile changes missed while disconnected.
      };
      socket.onmessage = (message) => {
        const hint = JSON.parse(message.data);
        if (hint.type === "notification.event") refreshSummary();
      };
      socket.onclose = (event) => {
        if ([4400, 4401, 4403].includes(event.code)) return;
        setTimeout(connectNotifications, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      };
    }

    connectNotifications();

Start this once per page/application instance. For busy feeds, debounce hint
refreshes and respect REST throttling rather than fetching for every event.
Refresh visible inbox/activity pages as well as counts when your UI needs
them. A hint can be duplicated, lost or followed by an authorization change;
the REST response remains authoritative. GET refreshes need no CSRF mutation
token; mark-read/clear actions still use normal authenticated REST writes.

Visibility and fan-out
----------------------

- Sent, unexpired notifications are delivered to direct recipients and
  current members of targeted Django groups (``DYNAMIC`` mode).
- In ``SNAPSHOT`` mode, fan-out uses the persisted direct-recipient snapshot;
  later group membership changes do not change the audience.
- Staff/superuser privileges **do not** grant personal inbox visibility.
- Inactive users, per-user soft deletions and optional-category opt-outs are
  excluded. Mandatory categories bypass opt-outs.
- Recipient resolution is database-backed, bounded to 500 user IDs per page,
  and does not pre-materialize large audiences. On socket delivery, the
  consumer rechecks current visibility to avoid leaking recently revoked
  group permissions or newly disabled preferences.
- A per-user Channels group name uses a keyed digest rather than a raw PK;
  it is never selected by an untrusted client.
- State events (seen, unseen, cleared) only go to the user that changed state,
  preserving independent read/deletion states for group members.

All event queries use the configured ``DJANGO_NOTIFICATION_CHANNELS_DATABASE_ALIAS``
(default ``'default'``). Events from another database alias are ignored. The
host application's authenticated user must refer to the same user database.

Limitations
-----------

By default, this integration is **best-effort**: it listens to post-commit
signals in the API process. Large fan-outs can increase commit-callback
latency, and crashes or channel-layer outages can lose hints.

To persist events before delivery, enable the package's :doc:`outbox` mode
(``DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"``), register this same
Channels adapter **in the outbox worker process**, and run
``process_notification_outbox``. In this mode, channel-layer exceptions cause
outbox retries instead of being swallowed, but a partial fan-out can be
replayed. Duplicate hints are therefore expected. A Channels group send only
acknowledges enqueueing a message in the channel layer, not browser delivery.

WebSocket disconnects, expiring channel-layer messages, reconnects, membership
changes and other failures can still lose hints. Keep REST inbox
reconciliation available regardless of delivery mode.

The events ``notification.hard_deleted`` and aggregate/bulk ``sent``
events cannot identify their audience **after the fact** and are ignored.
``mark_all_as_sent()`` also emits individual sent events, which do generate
authorized WebSocket hints. Direct model writes outside the lifecycle service, group
membership/preference changes, expiration and retention cleanup also do not
produce automatic pushes. Reconnects must refetch the inbox. The adapter does
not persist websocket delivery receipts or messages, and makes no exactly-once
guarantee. Long-lived sockets re-check user active status on delivery, but
host session revocation policies should explicitly close existing sockets.

Clients should not treat WebSocket event ordering as authoritative. Always
reconcile using REST after reconnect or suspected missed messages.
