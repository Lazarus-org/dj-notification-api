Notification lifecycle events
=============================

The package exposes a lightweight Django signal for optional integrations.
The default signal path requires no Redis, Celery, Channels or broker.
For durable event intent, enable the optional transactional :doc:`outbox`. The event payload
contains **identifiers and state metadata only**, never a serialized
notification, group membership, message body, or user contact information.

Register a receiver
-------------------

Connect a receiver once during your Django application's ``AppConfig.ready()``
(or import a dedicated receivers module from there)::

    from django_notification.events import notification_event, NotificationEventKind

    def handle_notification_event(sender, event, **kwargs):
        if event.kind != NotificationEventKind.CREATED or not event.is_sent:
            return
        # Re-fetch using event.database and event.notification_id.
        # Re-evaluate channel permissions and user preferences before delivery.
        # This callback is best-effort; do not assume it will run exactly once.

    notification_event.connect(
        handle_notification_event,
        dispatch_uid="my-app-notification-handler",
    )

The argument ``event`` is a frozen ``NotificationEvent`` dataclass with:

- ``kind``: one of the ``NotificationEventKind`` constants;
- ``database``: Django database alias for re-fetching;
- ``notification_id``: set for single-object operations, otherwise ``None``;
- ``user_id``: set for per-user state operations, otherwise ``None``;
- ``batch`` and ``affected_count``: aggregate operations omit the affected IDs;
- ``is_sent``: present for creation and update/sent operations when relevant;
- ``fields``: changed field names for a notification update.

Created, updated, sent, seen, unseen, cleared and hard-deleted events are
emitted from the package lifecycle service. A draft transitioned to sent by
``update_notification(is_sent=True)`` emits both ``updated`` and ``sent``;
``mark_all_as_sent()`` emits an individual ``sent`` event for each changed
notification, followed by the legacy aggregate ``sent`` event without IDs.
Rows are selected in bounded keyset pages, and all updates and outbox intent
share one transaction. Integration receivers should ignore the aggregate to
avoid duplicate work. ``Notification.mark_as_seen()``
emits the same kind of read event through its legacy compatibility path.
Direct low-level ORM writes, queryset
``.update()``/``.delete()``, ordinary Django admin edits and the expiration cleanup
command do not emit these lifecycle events. The admin ``mark_as_sent`` action
uses the lifecycle service and does emit per-notification sent events. There is no automatic
``expired`` or ``delivered`` event.

Transaction and reliability guarantees
--------------------------------------

Events are dispatched using ``transaction.on_commit()`` on the correct
database alias. Rolled-back transactions do not dispatch their events. A
nested transaction waits for its outermost successful commit. Repeated
idempotency creation does not re-emit ``created``; sequential no-op read
transitions do not re-emit state changes. Batch counts reflect the eligible
rows identified by the service and **may not equal newly persisted rows under
concurrent races**.

In the default ``"signal"`` mode, events are **best-effort and in-process**, not durable: a process crash after
commit can lose an event; deliveries are not replayed; receivers can run more
than once with overlapping callers. Receiver errors are swallowed via Django's
``send_robust`` and logged without exception messages or notification data.
Do not use this interface alone for billing, audit trails, guaranteed outbound
delivery, or critical work. Enable the package's optional :doc:`outbox` when durability is required. Receivers should be short-running;
for real-time clients or external channels use a separately deployed optional
adapter and enforce authorization at delivery time.

Optional WebSocket bridge
-------------------------

The optional Channels adapter is documented in :doc:`channels`. It sends
authorized, ID-only invalidation hints to authenticated user sockets. The
core package does not install or import Django Channels.
