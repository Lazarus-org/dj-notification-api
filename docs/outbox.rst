Transactional notification outbox (optional)
============================================

The outbox is **opt-in**. By default, the package still emits an in-process
``notification_event`` signal after each successful commit. Enabling the outbox
persists the same minimal event payload in the *same database transaction* as
the notification change, without invoking external receivers inline.

Configuration
-------------

Apply Django migrations, then enable the option in ``settings.py``::

    DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"

The two supported settings values are ``"signal"`` (default) and ``"outbox"``.
The mode is validated by Django system checks. Switching to outbox mode does
not require Redis, Celery, Channels, or another broker. The model and migration
are installed in either mode, but no outbox rows are produced in the default
``"signal"`` mode.

Register your receivers in the **worker process** as well as the application
process, normally from a host application's ``AppConfig.ready()``::

    import logging
    from django_notification.events import notification_event

    logger = logging.getLogger(__name__)

    def on_notification(sender, event, outbox_event_id=None, **kwargs):
        logger.info(
            "Notification event handled event=%s kind=%s database=%s",
            outbox_event_id, event.kind, event.database,
        )

    notification_event.connect(
        on_notification, dispatch_uid="my-app-notification-event",
        weak=False,
    )

This receiver demonstrates observable dispatch without external side effects.
Put registration in an installed application's ready() method, or import the
receiver module from there. Replace the log action with your application
integration and preserve replay safety. The supplied delivery/Channels adapters
already register their own receivers; do not also send the same messages from
an extra receiver unless duplication is intentional.

Run one bounded pass (suitable for scheduling periodically)::

    python manage.py process_notification_outbox --batch-size=100

Or run a continuously polling process under a process supervisor::

    python manage.py process_notification_outbox --loop --poll-seconds=2

Database aliases are isolated. For non-default aliases, use ``--database``
and configure receivers accordingly. A Channels adapter must be explicitly
connected in the worker process using ``connect_notification_channels()`` and
configured against the same database alias. For production with multiple
workers, use PostgreSQL or another backend supporting safe row-level claiming.

Reliability contract
--------------------

- Every lifecycle event emitted through the package service is inserted before
  the enclosing mutation transaction commits; rollback removes both writes.
- Each worker claims a pending event using a short transaction and an expiring
  lease. Receiver callbacks execute outside that transaction.
- Failed callbacks are retried with capped exponential backoff. The default
  limit is five attempts; terminal rows remain ``FAILED`` for inspection.
- An abandoned ``PROCESSING`` claim is reclaimed after its lease expires.
  A worker cannot acknowledge a claim that another worker has since acquired.
- An event is marked ``DELIVERED`` only after all registered Django-signal
  receivers finish without raising. No registered receivers counts as failure.
- **At least once, not exactly once**: if a process crashes after the external
  effect but before its acknowledgement, the event can be replayed. Receivers
  should deduplicate using ``outbox_event_id`` and design idempotent effects.
- ``DELIVERED`` only means the receiver accepted an event. For Channels this
  means the channel layer accepted a message; it does *not* guarantee that a
  connected browser actually received, displayed or acknowledged it.
- Neither a strict cross-worker delivery order nor a durable user-by-user
  broadcast history is guaranteed. Group fan-out may partially succeed and
  replay, generating duplicate invalidation hints. REST reconciliation is
  still required for clients, particularly for aggregate events.
- The outbox **does not capture** direct ORM writes, Django admin changes or
  pruning jobs that bypass the package lifecycle service.

No notification content, contact details, creation keys, or exception messages
are stored in an outbox event payload. The payload contains ``kind``, IDs,
state fields and counters; do not expose the outbox table through the public
HTTP API. Event rows intentionally do not use a foreign key to the source
notification because hard deletion must not erase undelivered events.

Retry and maintenance operations
--------------------------------

Adjust the worker limits as necessary::

    python manage.py process_notification_outbox \
      --max-attempts=5 \
      --lease-seconds=60 \
      --retry-base-seconds=5 \
      --retry-max-seconds=3600

The lease should exceed normal receiver execution time. Crashed last-attempt
leases become terminal failures rather than remaining stuck forever. When a
problem has been corrected, explicitly requeue specific failed IDs::

    python manage.py requeue_notification_outbox 15 16

Requeuing *never* changes delivered or in-progress events. It resets the retry
counter of the selected failed rows. Review and fix the receiver or external
service before replaying; already-performed external side effects may recur.

Delivered rows accumulate until they are cleaned up. Inspect with a dry run,
then remove old delivered rows only when replay/deduplication retention permits::

    python manage.py prune_notification_outbox
    python manage.py prune_notification_outbox --execute --older-than-days=30

The maintenance command does not delete pending, processing, or failed rows.
Choose retention long enough for downstream event-ID deduplication.

Limitations and deployment guidance
-----------------------------------

A database outbox avoids the crash gap between committing business state and
recording delivery intent. It does not make sending external messages atomic
with SQL commits. Receivers performing irreversible effects should maintain
their own durable deduplication record keyed by ``outbox_event_id``. Monitor
outbox queue depth, oldest pending event age, stale claims, and failed counts.

Start with a single worker for simple deployments. Multiple workers can claim
in parallel on PostgreSQL using ``SELECT FOR UPDATE SKIP LOCKED`` and token-
guarded acknowledgements. The fallback claim path relies on conditional
updates but should receive database-specific concurrency tests before use
under heavy load. Do not depend on an in-memory Channels layer for delivery
between distinct application and worker processes.

Related: :doc:`events` and :doc:`channels`.

Follow one event through a crash
--------------------------------

Consider an event with two receivers, A and B:

1. The notification transaction commits its content and outbox row together.
2. A worker claims the row and gives it a lease token/deadline.
3. A succeeds, then B raises. The event is not acknowledged as delivered.
4. After backoff, the event is dispatched again. A can run again too.
5. Only when every registered receiver succeeds can the row be acknowledged.

A receiver that stores an event ID after an external request still has a crash
gap between provider acceptance and saving that marker. Prefer a provider
idempotency key, or make the receiver's database-only effect and its marker
atomic in the same database transaction. Merely checking a marker before
sending does not make the external effect exactly once.

No registered receiver is a failure rather than silent acknowledgement.
However, a missing intended receiver cannot be inferred if another receiver
is registered and succeeds. Verify actual receiver registration in worker
processes, not only web startup. A permanently broken receiver can exhaust
the event's retry budget; correct it before targeted requeue.

Queue states
-------------

PENDING rows become eligible at available_at. A successful claim changes the
row to PROCESSING with a finite lease. Successful callbacks produce DELIVERED;
failed callbacks return it to PENDING with a delay until the retry budget is
exhausted, when it becomes FAILED. A process that crashes leaves PROCESSING
until the lease expires and another worker reclaims or terminally fails it.
An old owner cannot acknowledge a newer owner's token.

Requeue resets only selected FAILED rows. It does not interrupt current
claims. Outbox retention removes only sufficiently old DELIVERED rows. Monitor
ready age, stale/stranded leases and failures using :doc:`operations`.
