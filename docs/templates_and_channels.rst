Localized delivery templates and channel preferences
====================================================

Localized templates and per-channel preferences extend the optional external delivery worker.
It does not introduce mandatory external dependencies or change the personal
notification inbox semantics. Enable the transactional outbox and run both the outbox and external delivery
workers before using delivery backends.

Message templates
-----------------

``NotificationTemplate`` defines a message for a managed category, a delivery
channel and a locale. Only ``email``, ``sms`` and ``push`` are templated.
Webhooks stay **identifier-only** and never gain notification body content.
Templates are not required: when a matching active template does not exist,
email delivery retains its original verb/description/link output. Custom
SMS/push backends may use the same fallback by calling ``render_delivery``.

For example, add templates using the Django admin or trusted application code::

    from django_notification.models import NotificationTemplate

    NotificationTemplate.objects.create(
        category_id="general", channel="email", locale="en",
        subject="Update: $verb",
        body="${description}\n\n$link",
    )

    NotificationTemplate.objects.create(
        category_id="general", channel="email", locale="fa",
        subject="$verb",
        body="${description}\n\n$link",
    )

Template syntax uses **Python string.Template**, not Django's template engine.
Only ``$verb``, ``$description``, ``$link``, ``$category`` and ``$priority`` are
accepted. ``$$`` represents a literal dollar sign. Arbitrary fields,
attribute traversal, filters and template tags are deliberately unsupported.
Admin/model validation rejects unsupported variables and malformed templates.
No recipient information or arbitrary ``notification.data`` enters rendering.

The delivery worker checks enabled templates in this order: exact recipient
locale, its base language, the configured default locale, its base language.
Recipients may expose an optional ``notification_locale``,
``language_preference``, or ``language_code`` field/property (in that order).
Otherwise the worker uses ``DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE``,
which defaults to Django ``LANGUAGE_CODE``. Supported normalized language tags
look like ``en``, ``fa`` or ``en-us``; invalid per-user values fall back to the
default. The setting is validated by Django system checks.

To render email, the supplied ``DjangoEmailBackend`` works automatically. For
custom SMS or push providers, opt in to rendering explicitly::

    from django_notification.delivery.backends import DeliveryBackend
    from django_notification.delivery.rendering import render_delivery

    class MySMSBackend(DeliveryBackend):
        def send(self, delivery, *, idempotency_key):
            message = render_delivery(delivery)
            # Call your provider with message.body and a validated destination.
            # Pass idempotency_key to the provider if supported.

Rendering occurs immediately before each delivery attempt. **Template edits
can change the body of a pending or retried message.** The delivery job does
not retain rendered bodies or recipient contact details. Keep templates stable
for in-flight events, or introduce immutable template versions for workloads
that require an exactly reproducible message payload.

Per-user channel preferences
----------------------------

``NotificationChannelPreference`` defines an override for one user, managed
category and external channel (``email``, ``sms``, ``push`` or ``webhook``).
Missing rows default to enabled. Category-level inbox opt-outs remain separate:
a disabled optional category suppresses the personal inbox and external
fan-out; disabling email alone does not suppress SMS or the inbox.

Mandatory categories cannot be disabled. The service enforces this policy at
both job enqueue and send time, even if an older, disabled override row exists.

The authenticated NotificationViewSet adds the following routes, under the
existing configured notification URL prefix::

    GET   /notifications/channel_preferences/
    PUT   /notifications/channel_preferences/{category_slug}/{channel}/
    PATCH /notifications/channel_preferences/{category_slug}/{channel}/

Example request body::

    {"enabled": false}

The response for an entry contains ``category``, ``channel``, ``mandatory``
and effective ``enabled``. A valid ``true`` resets the override, restoring
default behavior. Unknown channels/categories return HTTP 404. Attempts to
disable a mandatory category return HTTP 400. All actions are scoped to the
authenticated request user.

When enqueueing deliveries, the service skips channels disabled by current
preferences, loading overrides for bounded batches of recipients. Workers
recheck both notification eligibility and channel preference immediately before
contacting the provider. Already-queued jobs can therefore be cancelled if a
user opts out. Such cancellations are not automatically reactivated if the
user later opts in; future notifications can create new jobs.

Opting in does not replay cancelled jobs. Provider retries remain at least
once; see :doc:`delivery` for acceptance, failure classification and recovery.

Choosing a locale: worked example
---------------------------------

Suppose a recipient's notification_locale is ``fr-CA`` and the deployment
default is ``en-us``. Normalization produces ``fr-ca`` and the lookup order
is ``fr-ca``, ``fr``, ``en-us``, ``en``. The first matching active template
for the notification's category and channel wins. A disabled fr-ca template
does not prevent fallback to an active fr template. If none exists, rendering
uses the notification verb/description/link fallback.

The category key, channel and normalized locale identify a catalog entry.
Create separate entries for translated subject/body content rather than
putting locale conditionals in a template. Variables are plain text
substitutions; they do not run Django template syntax or user properties.

For example, this catalog entry uses a literal dollar sign and an allowed
description variable::

    NotificationTemplate.objects.create(
        category_id="general",
        channel="email",
        locale="en",
        subject="Account update",
        body="Balance changes use $$ notation. ${description}",
    )

Validate edits before saving from custom administration code. The worker
validates again because bulk SQL updates can bypass model validation; a
malformed persisted template must fail rather than evaluate arbitrary text.
