Troubleshooting
================

Diagnose the layer where progress stopped before retrying work. An inbox row,
an outbox event, a delivery job and a WebSocket hint have different lifecycles.

The inbox is empty
-------------------

Start with the same account used by the failing request. In a trusted Django
shell, inspect an expected notification without relaxing API permissions::

    from django_notification.models import Notification

    notification = Notification.objects.get(pk=expected_id)
    notification.is_sent
    notification.expires_at
    notification.category_id

    audience = Notification.objects.visible_to(user)
    audience.filter(pk=expected_id).exists()

    personal = audience.active_at().sent_only().not_deleted_by(user)
    personal.unseen_by(user).filter(pk=expected_id).exists()
    personal.seen_by(user).filter(pk=expected_id).exists()

Replace expected_id and user with the actual ID/account. Interpret the result:

* Not in visible_to: check direct targeting, current dynamic group membership,
  snapshot recipients, account active state and optional-category opt-out.
* Visible but not personal: check send state, expiry and personal clearing.
* In seen_by but not unseen_by: use the activity list or mark it unseen.
* In the query but not the first REST page: inspect pagination and query filters.
* Works for the recipient but not an administrator: this is expected unless
  the administrator is also a recipient. Staff does not bypass audience rules.

``public=True`` does not broadcast content. Adding a user to a group after a
SNAPSHOT notification was created does not grant that earlier notification.

Detail gives 404 after marking read
------------------------------------

``notifications/{id}/`` is unread detail. Once read, use
``activities/{id}/`` or ``notifications/{id}/preview/``. Preview covers both
read states while retaining sent, expiry, deletion and audience checks.

If preview also fails, refresh summary/feeds: access may have changed through
membership, opt-out, clearing or expiration. Do not automatically retry a
state mutation forever on 404.

Writes fail with 403 or 405
----------------------------

For 403, check authentication, the configured extra permission and session
CSRF requirements. A successful GET does not establish that an unsafe request
has a valid CSRF token. Use the same authentication scheme as the host app.

For 405, verify the method and enabled features. GET mutations are disabled
by default. Use POST for mark-seen/mark-unseen and DELETE for clearing.
Hard-delete routes additionally require explicit enablement and staff access.
Do not enable legacy mutation GETs just to bypass a client CSRF issue.

Bulk action changed nothing
-----------------------------

Selected operations are atomic. One inaccessible, expired or cleared ID can
cause 404 for the entire selection. A clear selection must contain seen items.
The body must be ``{"ids": [...]}``, with 1–500 entries before deduplication.
A processed count includes IDs already in the desired state.

For a filtered page, send its IDs to a selected bulk endpoint. Adding
``?category=orders`` to mark-all/clear-all does not scope those manager actions.

No delivery job appears
------------------------

Check configuration and work in this order:

1. Run ``python manage.py check``.
2. Confirm EVENT_DELIVERY is outbox and DELIVERY_BACKENDS contains the channel.
3. Confirm the host AppConfig calls connect_notification_delivery in every
   outbox worker process, not just the web server.
4. Create a new notification with is_sent=True through the manager, or send a
   draft using update_notification. Plain ORM updates produce no event intent.
5. Run one outbox pass and inspect notification_queue_health/failure_report.
6. Check audience, category/channel opt-outs and routing for that recipient.

A backend added after content was sent does not backfill it. An event marked
DELIVERED means registered receivers completed; if the delivery receiver was
absent, another receiver could have acknowledged the event without creating
jobs. Correct registration before deciding on a carefully scoped recovery.

A job exists but no message arrives
------------------------------------

.. list-table::
   :header-rows: 1

   * - Job state
     - Check
   * - PENDING
     - Is available_at in the future because of backoff, digest or quiet hours?
   * - PROCESSING
     - Is the worker still active, or will an expired lease be reclaimed?
   * - FAILED
     - Inspect sanitized attempt codes, fix the cause, then explicitly requeue
   * - CANCELLED
     - Check recipient access, expiry, preferences and current routes
   * - DELIVERED
     - Check provider acceptance/receipts; this is not proof of device delivery

Verify you started process_notification_deliveries, not only the outbox
worker. Confirm EMAIL_BACKEND is not still console/locmem. Missing recipient
email is permanent failure. Requeue failed digest envelopes with the digest
command; requeueing direct jobs is not a substitute for envelope recovery.

Seeing duplicate external sends
--------------------------------

A crash or timeout after acceptance can cause replay. Make receiver effects
idempotent, forward the provider idempotency key and keep timeouts below
leases. Running multiple registered receivers that independently send the
same effect can also duplicate it. Register one receiver with a stable
dispatch_uid. SMTP cannot provide exactly-once delivery.

Messages do not leave quiet hours
----------------------------------

Inspect the user's stored timezone and both quiet-hour boundaries. Quiet
windows use local wall time, including midnight/DST transitions. Equal
boundaries disable quiet hours. DAILY is next local day at 09:00; WEEKLY
is next Monday at 09:00, even when created on Monday.

Changing cadence/timezone affects newly enqueued work. Existing available_at
timestamps are not automatically pulled forward when quiet hours are removed.
Use :doc:`schedules_and_digests` to interpret slots and envelope recovery.

WebSocket connects but receives nothing
----------------------------------------

Check these independently:

* Use ASGI, authenticated scope and the ws/notifications/ route.
* Register connect_notification_channels where events are processed.
* Configure a shared Redis layer for multiple processes. In-memory layers
  cannot carry a message from a separate outbox worker to an ASGI process.
* Match CHANNELS_DATABASE_ALIAS to the event/worker database.
* Create/send through the manager after the database transaction commits.
* Check that the user is still active and eligible for the notification.

Close code 4401 means missing authenticated identity, 4403 means the account
is no longer active/available, 4400 rejects client commands, and 1011 indicates
a missing channel layer at connection. The socket is server-to-client only.
It does not accept subscription commands or mark-read messages.

On reconnect, refresh REST state. Hints can be lost or duplicated and are not
an offline event history. See :doc:`channels` for origin validation and ASGI
authentication setup.

Collect useful diagnostics
---------------------------

Include the installed package/Python/Django/DRF versions, database backend,
relevant sanitized settings, failing HTTP method/path/status, and aggregate
queue/failure output. State whether the issue affects in-app visibility,
outbox dispatch, external delivery or sockets.

Remove notification bodies, recipient contacts, tokens, credentials, webhook
secrets and raw provider responses before sharing an issue. Preserve a minimal
reproduction with two users if the problem involves recipient isolation.
