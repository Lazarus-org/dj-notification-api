Historical Delivery Analytics
=============================

The package provides **read-only, aggregate historical delivery reporting** using
existing ``NotificationDelivery`` and ``NotificationDeliveryAttempt`` records.
No models, migrations, external metric provider, or optional delivery backend
are required. It is available to **trusted Django operators via a management
command**, not as an unauthenticated HTTP API.

Commands
--------

::

    # Human-readable summary (last 30 days)
    python manage.py notification_delivery_report

    # JSON, with daily UTC cohorts and aggregate distributions
    python manage.py notification_delivery_report --days=7 --json

    # Export aggregated channel/category/priority rows (not individual jobs)
    python manage.py notification_delivery_report --days=90 --csv > delivery.csv

    # Limit the number of individually named categories to five
    python manage.py notification_delivery_report --category-limit=5 --json

The ``--database`` option selects a configured Django database alias.
``--days`` accepts 1–365 days, inclusive. ``--category-limit`` accepts 1–50.
The importable API is
``django_notification.operations.analytics.notification_delivery_analytics``.
It accepts the same options, plus an optional aware ``now`` for consistent
snapshots or deterministic tests.

Counting and timing semantics
-----------------------------

A report includes **delivery jobs created** in the half-open UTC interval
``[report_time - days, report_time)``. Each job's status is sampled at query
time. This is a *creation cohort*, not a log of historical status transitions:
rerunning a report for an older cohort can change counts after retries or
requeue operations. There is no cross-query transactional snapshot lock.

- **Terminal success rate** = delivered / (delivered + failed), as a percentage.
  Pending, processing, and cancelled jobs are deliberately not in its
  denominator. With no terminal jobs, the rate is ``null``, not zero.
- **Average and maximum queue latency** measure seconds from delivery-job
  creation to ``delivered_at``. They include waiting, retries, quiet hours and
  digest scheduling, and are **not** SMTP/SMS/network round-trip latency.
  Invalid negative and missing timestamps do not contribute to these measures.
- **Latency distribution** has mutually exclusive ranges: under 5 seconds,
  5–30 seconds, 30 seconds–5 minutes, 5–60 minutes, and at least one hour.
- **Job claim distribution** counts persisted worker claims (0, 1, 2, 3–4,
  at least 5), not necessarily provider invocations. Leases may be reclaimed.
- **Attempt outcomes** count persisted backend attempt-history rows for jobs
  in the cohort whose completion time precedes the report cutoff.
- **Daily cohorts** are grouped by the UTC date of job creation and contain
  current total, delivered and failed counts; empty days appear as zeros.
- **Channel** and **priority** are fixed, low-cardinality dimensions; unknown
  stored values roll into ``other`` rather than being echoed untrusted.
  **Category** groups show up to the requested number of top categories;
  all remaining and invalid category slugs roll into ``other``.

The result does **not** contain notification messages, templates, raw provider
responses/error codes, email addresses, user/recipient IDs or notification IDs.
Category slugs are application-defined labels and should be kept non-sensitive.
Operations teams should protect management-command access and exported reports,
especially for small cohorts where even aggregates can be sensitive.

Retention and limitations
-------------------------

Hard-deleting a notification cascades its delivery jobs and attempt histories.
Pruned or deleted records cannot be reconstructed by this reporting API.
Reports should not be treated as immutable historical audits or provider-level
delivery receipts: ``DELIVERED`` means the configured backend accepted a send,
not that a device displayed the message or a human read it. Some external
providers can retry or acknowledge asynchronously.

For long-term reporting, export aggregates before pruning their source rows
and define how corrections/requeues affect your downstream snapshots.
The package does not retain a separate immutable analytics ledger.
