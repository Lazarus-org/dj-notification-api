Send email and external notifications
======================================

External delivery creates one job per notification, recipient and configured
channel. Email, SMS, push and webhook jobs have independent outcomes. Reading
the in-app notification does not mark a job delivered, and delivery failure
does not remove an otherwise eligible inbox item.

This guide starts with console email so you can verify the full workflow
without SMTP credentials, then explains production and custom adapters.

Configure a working email integration
--------------------------------------

Add to your Django settings::

    DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS = {
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "notifications@example.com"

Register the delivery receiver in an installed application::

    # myapp/apps.py
    from django.apps import AppConfig

    class MyAppConfig(AppConfig):
        name = "myapp"

        def ready(self):
            from django_notification.delivery import connect_notification_delivery
            connect_notification_delivery()

Use ``"myapp.apps.MyAppConfig"`` in INSTALLED_APPS. This initialization must
run in web processes and outbox workers. The registration is idempotent and
validates configured backend classes. An installed backend mapping without
receiver registration does not materialize delivery jobs.

Apply migrations and check configuration::

    python manage.py migrate
    python manage.py check

Create a sent notification for a saved user with a nonblank email address::

    from django.contrib.auth import get_user_model
    from django_notification.models import Notification

    User = get_user_model()
    recipient = User.objects.get(**{User.USERNAME_FIELD: "sam"})
    notification = Notification.objects.create_notification(
        actor=recipient,
        recipients=[recipient],
        verb="Your report is ready",
        description="Open your dashboard to download it.",
        is_sent=True,
        idempotency_key="reports:weekly:2026-01-05:sam",
    )

Use an event-specific key for your own workload. If running the example inside
an outer transaction, commit it before starting the workers.

Run one pass of each worker::

    python manage.py process_notification_outbox --batch-size=100
    python manage.py process_notification_deliveries --batch-size=100

The first worker dispatches persisted lifecycle events and creates delivery
jobs. The second prints an email through Django's console backend. Neither
command loops unless ``--loop`` is supplied. A delivered outbox event alone
does not mean the email worker has run.

Check the result in Django shell::

    from django_notification.models import NotificationDelivery

    jobs = NotificationDelivery.objects.filter(notification=notification)
    list(jobs.values("channel", "status", "attempts"))
    # One email job should be DELIVERED after the console backend accepts it.

If no job exists, work through :doc:`troubleshooting` before replaying events.

Use a real email backend
-------------------------

Replace EMAIL_BACKEND with Django's SMTP backend or an installed application
email backend and configure its usual settings::

    import os

    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ["EMAIL_HOST_USER"]
    EMAIL_HOST_PASSWORD = os.environ["EMAIL_HOST_PASSWORD"]
    EMAIL_TIMEOUT = 15
    DEFAULT_FROM_EMAIL = "notifications@example.com"

Choose your actual provider's host, port and TLS requirements. The built-in
adapter reads the recipient's current email address immediately before the
attempt. A missing/blank address is a permanent failure. Without a template,
the subject uses the notification verb and the body uses description (or verb)
plus the link when present. Email subjects are normalized to one line.

The console backend reports acceptance without sending to the internet. SMTP
acceptance likewise does not establish eventual mailbox delivery or reading.

Run workers in production
---------------------------

Run both processes under your process supervisor::

    python manage.py process_notification_outbox --loop --poll-seconds=2
    python manage.py process_notification_deliveries --loop --poll-seconds=2

Both commands share these controls:

.. list-table::
   :header-rows: 1

   * - Option
     - Default
     - Meaning
   * - --database
     - default
     - Alias containing notification and queue records
   * - --batch-size
     - 100
     - Maximum work items processed per pass; 1–1000
   * - --max-attempts
     - 5
     - Retry budget; 1–100
   * - --lease-seconds
     - 60
     - Claim ownership window; 5–3600 seconds
   * - --retry-base-seconds
     - 5
     - Initial retry delay
   * - --retry-max-seconds
     - 3600
     - Maximum delay; base <= maximum <= 86400
   * - --poll-seconds
     - 2
     - Idle polling interval with --loop; 0.1–3600 seconds

The delivery worker processes direct jobs and due digest envelopes, alternating
them to avoid starving either kind. Future digest work is not immediately
ready backlog. No separate digest process is needed.

Use PostgreSQL for multi-worker row locking. Keep network timeouts below the
lease and allow room for all work in an attempt, particularly multi-recipient
event fan-out. Network calls run outside database claim transactions.
There is no lease heartbeat extending a claim during a long provider call;
a call exceeding its lease can race a reclaim and cause duplicate effects.

Retry classification
---------------------

The built-in service records sanitized attempt outcomes:

.. list-table::
   :header-rows: 1

   * - Adapter result
     - Job handling
   * - Returns normally
     - DELIVERED, accepted attempt
   * - RetryableDeliveryError
     - PENDING after backoff, or FAILED at the retry limit
   * - PermanentDeliveryError
     - FAILED without automatic retry
   * - Invalid backend configuration
     - Direct job fails with backend_config
   * - Unexpected exception
     - Retry using a generic backend_error code
   * - Recipient no longer eligible
     - CANCELLED before provider invocation
   * - Quiet hours still active
     - Deferred without consuming a provider retry

Backoff is capped exponential: with defaults, retries wait 5, 10, 20, 40
seconds, continuing up to the cap when a larger budget is configured.
Attempts record outcomes, not raw exception messages or provider payloads.
Digest retries belong to their envelope; see :doc:`schedules_and_digests`.

A custom backend you can run locally
-------------------------------------

This backend demonstrates the complete extension contract without assuming a
provider SDK. It logs only job metadata; it is for local integration checks,
not a transport to end users::

    # myapp/delivery.py
    import logging
    from django_notification.delivery.backends import DeliveryBackend

    logger = logging.getLogger(__name__)

    class MetadataBackend(DeliveryBackend):
        def send(self, delivery, *, idempotency_key):
            logger.info(
                "Notification delivery accepted job=%s channel=%s key=%s",
                delivery.pk, delivery.channel, idempotency_key,
            )

Configure it under one of the supported channel names in
DJANGO_NOTIFICATION_DELIVERY_BACKENDS. Enable INFO logging for myapp.delivery
to see its output. A normal return marks the job accepted.
Your real SMS/push adapter should instead resolve a validated current
destination, call its provider with a bounded timeout, propagate the stable
idempotency key and classify rejections using the error classes above.
Returning before acceptance would incorrectly mark delivery complete.

The ``delivery`` argument has notification and recipient model instances.
Use ``render_delivery(delivery)`` from
``django_notification.delivery.rendering`` for restricted localized
templates. The stable key for an individual job is
``djnotify-delivery:{delivery_id}``. Providers that support idempotency should
retain it across retries. The base ``send_digest()`` rejects digests;
email is the supported scheduled digest channel.

Signed webhooks
----------------

Enable the built-in webhook backend and configure a trusted endpoint::

    import os

    DJANGO_NOTIFICATION_DELIVERY_BACKENDS = {
        "webhook": "django_notification.delivery.backends.SignedWebhookBackend",
    }
    DJANGO_NOTIFICATION_WEBHOOK_URL = "https://events.example.com/notifications"
    DJANGO_NOTIFICATION_WEBHOOK_SECRET = os.environ["NOTIFICATION_WEBHOOK_SECRET"]

The POST body contains only these fields::

    {
      "type": "notification.delivery",
      "delivery_id": 17,
      "notification_id": 42,
      "recipient_id": 9,
      "channel": "webhook"
    }

Verify the ``X-Notification-Signature`` header using the exact raw request
bytes, before parsing/re-encoding JSON::

    import hashlib
    import hmac

    def signature_matches(raw_body, received_header, secret):
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, received_header or "")

Store successful Idempotency-Key values at the receiving service to avoid
repeating effects. HMAC alone does not prevent replay. Use your endpoint's
normal access controls and a coordinated secret-rotation policy.

The adapter uses a 10-second timeout and accepts 2xx responses. Most 4xx
responses are permanent rejections; 408, 429, 5xx and transport errors retry.
Redirects are not followed. The URL must be operator-controlled HTTPS without
embedded credentials or a fragment; localhost and non-public IP literals are
rejected. Restrict outbound networking too: hostname validation does not
eliminate DNS rebinding. A notification's link never selects this destination.

Recovery and changing configuration
-------------------------------------

After correcting a provider problem, preview and requeue explicit failed jobs::

    python manage.py notification_failure_report --show-ids --limit=20
    python manage.py requeue_notification_deliveries 17 18 --dry-run
    python manage.py requeue_notification_deliveries 17 18

Requeue keeps attempt history. It can repeat an external effect after a
timeout or crash even if the original provider accepted it. Missing backends
pause their queued jobs; adding a backend does not backfill older notifications.
Creation of sent content and unsent-to-sent lifecycle transitions generate
intent. Direct ORM updates do not.

Eligibility, current routes, channel preferences and expiration are rechecked
before sending. A cancelled job is not revived by later opt-in or route
changes. Hard deletion cascades queue/history records. Use
:doc:`operations` for monitoring and :doc:`routing_rules` for channel policy.
