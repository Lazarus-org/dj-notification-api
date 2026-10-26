Notification delivery schedules, quiet hours and digests
========================================================

This feature adds **opt-in, per-user, per-channel** scheduling for the optional
external delivery system. Existing installations remain on immediate delivery
without extra configuration. No Celery, Redis, or background scheduler is
required; use the existing ``process_notification_deliveries`` worker.

End-user API
------------

An authenticated user can read their effective settings with::

    GET /notification/notifications/delivery_schedule/

Only that user's schedules are returned. With no stored preference a channel
uses ``IMMEDIATE``, the ``UTC`` timezone, and no quiet hours.

Update the current user's email schedule with::

    PUT /notification/notifications/delivery_schedule/email/
    Content-Type: application/json

    {
      "frequency": "DAILY",
      "timezone": "America/Los_Angeles",
      "quiet_start": "22:00:00",
      "quiet_end": "07:00:00"
    }

``PATCH`` is also supported, and a pair of null quiet-hour values disables
quiet hours. ``timezone`` must be an installed IANA zone; a quiet-hour
interval must have both endpoints. Equal endpoints disable quiet hours.
Neither route accepts a user/recipient ID. ``DAILY``/``WEEKLY`` are
supported only for **email**; ``sms``, ``push``, and ``webhook`` support
immediate delivery with optional quiet hours. Application-specific providers
own their rendering/provider behavior; the scheduling API still restricts
digests to email.

Scheduling semantics
--------------------

* ``IMMEDIATE`` sends as soon as the worker is able to process a job.
* ``DAILY`` groups eligible email notifications for the next **09:00 local**
  calendar day.
* ``WEEKLY`` groups eligible email notifications for **09:00 local Monday**
  following creation, and never retroactively includes a previously sent batch.
* Local quiet hours postpone work until the next end of the quiet interval.
  Ranges crossing midnight and daylight-saving transitions are handled.
* Notifications in **mandatory** categories and notifications with ``URGENT``
  priority always bypass quiet hours and digest batching. They still respect
  authorization and expiry checks.
* Digest batches contain up to **50 notifications per email**; excess pending
  items from the same slot generate additional emails as workers process them.
* A recipient's direct or group-derived authorization, deletion state,
  category preferences and expiration are rechecked before sending each
  notification. Ineligible entries are cancelled and not included.

The scheduler changes external delivery only. In-app notification list and
read-state APIs are independent. Changes to timezone/frequency affect **newly
enqueued** jobs; older digest envelopes keep their original time slot.
Clearing quiet hours does not accelerate an existing ``available_at`` timestamp,
although the worker reevaluates quiet hours when a job becomes due.

Workers and recovery
--------------------

The external delivery worker now processes both individual delivery jobs and due digest
envelopes::

    python manage.py process_notification_deliveries --loop --batch-size=100

Digests have a separate lease, retry state and row identity. Concurrent workers
must use a production database offering row-level locking (for example,
PostgreSQL). Failures use backoff; once a digest exhausts retry attempts, its
pending children become failed. Late fan-out into a completed or cancelled
slot reopens it only for pending children; delivered children are not resent.
Late children of a failed slot inherit its failed state and require the same
explicit requeue. To retry known failed batches explicitly::

    python manage.py requeue_notification_digests 3 4

Requeueing a digest can resend an email after an ambiguous provider outcome.
Email via Django SMTP is **at-least-once**, not exactly-once. Workers must run
continuously or on a regular schedule; notification creation does not send
automatically in the request transaction. Digest content is composed transiently
from existing templates and is not persisted to the database. The database
stores only recipient identifiers, schedule settings, envelope status and
references to the existing delivery jobs.

Schedule examples
------------------

.. list-table:: All times below are in the schedule's local timezone
   :header-rows: 1

   * - Input
     - Earliest scheduled time
   * - IMMEDIATE, created 14:00, no quiet hours
     - Now, subject to worker polling
   * - IMMEDIATE, created 23:00, quiet 22:00–07:00
     - Tomorrow 07:00
   * - DAILY, created 08:00
     - Tomorrow 09:00, not today 09:00
   * - WEEKLY, created Monday 08:00
     - Next Monday 09:00
   * - DAILY, tomorrow 09:00 falls inside quiet 08:00–10:00
     - Tomorrow 10:00; the digest slot remains tomorrow 09:00
   * - URGENT with any of these schedules
     - Immediate eligibility, still subject to authorization and expiry

These are eligibility times, not delivery deadlines. Worker load, provider
backoff and outages can delay acceptance. A digest with 51 eligible items
produces one email of up to 50 followed by another email for the remainder.

Across a spring-forward gap, an unavailable quiet-end wall time is normalized
forward to a valid instant. Across fall-back, both occurrences are considered
and the next future end is used. Use an installed IANA zone such as
America/New_York rather than a fixed UTC offset when the user's location
observes daylight saving.

Replace or patch a schedule
---------------------------

PUT replaces the schedule and requires frequency/timezone. Omitted quiet-hour
values reset to null. PATCH preserves unspecified stored values; on a channel
with no stored schedule it starts from IMMEDIATE, UTC and null boundaries.

Disable quiet hours explicitly with a paired null update::

    PATCH /notification/notifications/delivery_schedule/email/
    Content-Type: application/json

    {"quiet_start": null, "quiet_end": null}

Both boundaries are required together in the effective result. When changing
only one boundary with PATCH, its partner may come from the stored schedule.
An equal start/end disables quiet hours; it does not mean all-day silence.

Frequency/timezone changes affect new jobs. Quiet hours are checked again for
due work. Changing an already-enqueued immediate job to DAILY does not move
that job into a new digest; the cadence chosen at enqueue is retained.
