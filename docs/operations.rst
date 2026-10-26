Notification delivery observability and safe operator diagnostics
=================================================================

The package provides **read-only operational reporting** to the opt-in notification
outbox and external delivery systems. The core package still requires no
Prometheus, Redis, Celery, or Channels dependency for these commands.

Queue health
------------

The aggregate report covers three independent queues: ``outbox``, ``delivery``
(immediate external jobs only), and ``digest`` (scheduled digest envelopes).
Pending digest *children* are counted separately, because only their digest
envelopes can be claimed by the worker. This avoids wrongly interpreting
scheduled digest content as an immediate-delivery backlog.

Run a human-readable report::

    python manage.py notification_queue_health

Use JSON for scripts or Prometheus text exposition for a collector::

    python manage.py notification_queue_health --json
    python manage.py notification_queue_health --prometheus

The output includes each queue's total, pending, processing, delivered, failed
and cancelled counts, plus immediately due work, future-scheduled work, expired
leases, **stranded** processing rows without a lease deadline, and oldest due
age in seconds. Per-channel external job counts use fixed known channel names.
No notification content, recipient identity, event payload or provider response
is included. Metrics are aggregated from the selected Django database.

An operator or a monitoring job can enforce thresholds::

    python manage.py notification_queue_health \
      --max-ready=1000 \
      --max-oldest-seconds=900 \
      --max-failed=100 \
      --max-stranded=0 \
      --fail-on-unhealthy

With ``--fail-on-unhealthy``, the command exits nonzero on exceeded thresholds.
Without it, the command always reports the measurement rather than treating a
backlog as a command failure. Defaults are advisory examples, not universally
correct production SLOs. Customize them for your traffic and delivery cadence.
The report is a point-in-time snapshot, not a live streaming endpoint or a
transactional lock. It should be polled at a suitable interval by an external
monitoring agent if alerting is required.

The Prometheus output is uninstrumented text and does not open an HTTP server.
Serve it through a trusted collector/textfile exporter if wanted; **do not**
publish an unauthenticated debug/metrics API from this package. Fixed label
vocabularies prevent per-notification or per-recipient cardinality explosions.

Failure reports
---------------

Inspect counts of failures from the last 24 hours and sanitized backend codes::

    python manage.py notification_failure_report --json

For manual recovery, optionally include a maximum of 20 queue record IDs::

    python manage.py notification_failure_report --show-ids --limit=20

Use ``--since-hours=72`` to widen the time window. The report never includes
contact addresses, notification bodies, exception strings, payloads, user IDs
or notification IDs. Failure codes are restricted to safe identifiers. The
attempt-code summary covers retry/permanent-failure attempts, not only terminal
failed jobs; terminal counts use the ``failed_at`` window separately.

Recovery preview
----------------

The existing targeted requeue commands now accept a read-only ``--dry-run``::

    python manage.py requeue_notification_outbox 15 --dry-run
    python manage.py requeue_notification_deliveries 17 18 --dry-run
    python manage.py requeue_notification_digests 3 4 --dry-run

The default invocation without ``--dry-run`` retains its previous behavior:
only the specified FAILED rows are requeued. Previews do not lock future work
or guarantee the same rows will still be FAILED when the actual command runs.
Requeueing can repeat irreversible external side effects after an ambiguous
provider outcome, even if the original worker timed out or crashed. Review
recipient/channel policies and provider idempotency before replaying.

Operations and caveats
----------------------

* A processing row with an expired lease is eligible for worker reclaim; a
  processing row with no lease deadline is flagged as stranded for manual
  investigation and is **not** auto-reclaimed by the new reporting module.
* The oldest-due age is based on ``available_at`` for pending jobs and
  ``leased_until`` for expired processing leases. It is not the original
  notification age or the scheduled timestamp of a future digest.
* Historical terminal failures remain counted in the all-time health report
  until operator requeue or a separate retention policy is applied. Use the
  time-window failure report to distinguish new failures from old incidents.
* Non-default database aliases can be passed with ``--database``. Monitoring
  reads do not create, acknowledge, send, delete, or retry notifications.
* Counters and health commands do not verify that an external provider truly
  delivered a message to its recipient. Delivery state remains at-least-once
  provider acceptance, not proof of receipt.

Respond to an incident
----------------------

Use queue health to decide which worker needs attention. A growing outbox
queue with few delivery jobs points to event dispatch/registration. A healthy
outbox with growing direct-delivery readiness points to the delivery worker
or provider. Future scheduled digests are not ready backlog.

.. list-table::
   :header-rows: 1

   * - Observation
     - Investigate
     - Recovery
   * - Ready count and oldest-ready age both grow
     - Missing/stalled workers, database connectivity, provider latency
     - Restore worker capacity; watch due age decline
   * - Stale leases grow
     - Worker exits, calls longer than leases, database interruptions
     - Restore workers; expired leases are reclaimable
   * - Stranded leases are nonzero
     - PROCESSING rows have no deadline and cannot expire normally
     - Investigate the write/corruption path; ordinary FAILED requeue does not repair them
   * - Failed count grows
     - Configuration, invalid destinations, repeated provider rejection
     - Correct the cause, preview and requeue selected failed IDs
   * - Scheduled count is large but ready age is low
     - Future quiet-hour/digest work
     - Compare expected schedules before increasing workers

The ready metric is due PENDING work plus PROCESSING work with expired
leases. Oldest-ready age uses available_at for due jobs and leased_until for
expired claims. It is not the original notification age. Digest child jobs
are counted separately because their envelope controls when they can run.

For example, require alerts once any queue exceeds your own thresholds::

    python manage.py notification_queue_health --max-ready=200 --max-oldest-seconds=300 --max-failed=0 --max-stranded=0 --fail-on-unhealthy

Thresholds are per queue, use strictly greater-than comparisons, and are
advisory unless --fail-on-unhealthy is supplied. A failed health command does
not retry or modify work. Monitor process liveness and database availability
separately; an empty queue does not prove a worker is running.

Recover the right record type
-----------------------------

Start with failure diagnostics, fix the underlying cause, then use the command
for the failed queue. IDs are queue record IDs, not notification or user IDs::

    python manage.py notification_failure_report --since-hours=24 --show-ids --limit=20
    python manage.py requeue_notification_outbox 15 --dry-run
    python manage.py requeue_notification_outbox 15

Outbox replay invokes receivers again. Delivery replay calls a provider again.
Digest replay requeues a failed envelope and its failed children. A provider
may already have accepted a timed-out attempt; confirm its idempotency policy
before replaying. Requeue commands operate only on selected FAILED records,
not CANCELLED, DELIVERED or currently PROCESSING records.

Use --database consistently for health, worker and recovery commands. A
successful command against the wrong alias cannot repair another queue.
See :doc:`troubleshooting` for missing jobs and paused channels.

Apply retention deliberately
-----------------------------

Preview expiration cleanup and outbox retention independently::

    python manage.py prune_expired_notifications --older-than-days=30
    python manage.py prune_notification_outbox --older-than-days=30

Add --execute only after reviewing the selection. Expiration cleanup deletes
notifications after their expiry plus the retention interval, cascading their
personal state, delivery history and creation-key claims. Outbox retention
deletes old delivered events; pending, processing and failed events remain.
Both commands use bounded batches, not an all-or-nothing transaction across
the entire run. The expiration command supports batch sizes 1–1000; the
outbox command does too.

Choose notification retention to cover privacy, audit and retry/replay needs.
Deleting creation keys allows later retries to create new notifications.
Deleting delivery history changes analytics. Do not prune records needed by
your receiver's event-ID deduplication policy or incident investigation.
