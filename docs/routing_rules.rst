Notification delivery routing rules
===================================

The package supports **optional** database-managed channel routing. The routing
engine is intended for trusted operators. It is not a user-configurable rule
language and it does not evaluate arbitrary Python expressions, templates,
JSONPath, or notification payload fields.

All existing behavior is preserved when there are no enabled rules: every
configured backend receives one eligible job per recipient. Routing is only
used for **external** channel delivery; the user's in-app notification feed
and the persisted notification priority are unchanged.

Configure rules in the Django admin or trusted application code::

    from django_notification.models import NotificationRoutingRule

    # Start with email only for a category (including urgent notifications).
    NotificationRoutingRule.objects.create(
        name="Only marketing email", category_id="marketing",
        sort_order=10, action="REPLACE", channels=["email"],
    )

    # Escalate high-priority marketing notifications to an SMS provider.
    NotificationRoutingRule.objects.create(
        name="Escalate marketing", category_id="marketing",
        sort_order=20, min_priority="HIGH", max_priority="URGENT",
        action="ADD", channels=["sms"],
    )

The ``category`` may be null for a global rule. Optional
``notification_status`` matches the existing status choices exactly. The
priority range is inclusive, using the explicit order LOW, NORMAL, HIGH,
URGENT. These are delivery-routing inputs, not generic arbitrary predicates.

Ordered rule actions
--------------------

Rules are evaluated by ascending ``sort_order``, then global before
category-specific rules at the same order, then primary key. The initial set
is **all configured external channels**:

- ``REPLACE`` uses only the listed channels.
- ``ADD`` adds the listed channels.
- ``REMOVE`` removes the listed channels.

Later actions can override earlier ones. All outcomes are intersected with
configured backends, so a rule cannot enable an unconfigured provider. A rule
must use a nonempty list of distinct supported channels: ``email``, ``sms``,
``push`` or ``webhook``. Empty resulting sets are valid and create no jobs.
Model/admin validation rejects invalid configuration; corrupted persisted
rules fail closed with an error during route evaluation.

Privacy and runtime changes
---------------------------

Group/direct recipient eligibility, expiration, category preferences, user
channel opt-outs, quiet hours, digests and mandatory-category policies still
apply. Routing cannot override a per-user channel opt-out; mandatory categories
retain their existing exception to user opt-outs. Operators can nevertheless
limit the channels for mandatory categories through routing rules.

Rules are evaluated **before** enqueueing jobs and again immediately before
external delivery, including delivery through an email digest. Disabling an
allowed route therefore cancels pending jobs before provider invocation.
However, enabling a channel later **does not backfill historic or previously
cancelled jobs**. A routing change cannot revoke messages already accepted
by a provider. Use an application-owned, carefully scoped reconciliation path
if backfill is required; blindly replaying all old notifications is unsafe.

With many active rules, routing adds lookups at enqueue and send time.
Measure this cost with representative traffic before adding a large catalog.

Work through an ordered policy
------------------------------

Suppose email, sms and push are configured. A global rule at sort_order 10
replaces the channel set with email. A category-specific orders rule at the
same sort_order adds push. A later orders rule at sort_order 20 adds sms for
HIGH through URGENT priority.

.. list-table:: Channels before user preferences and scheduling
   :header-rows: 1

   * - Notification
     - Selected channels
   * - General category, NORMAL priority
     - email
   * - Orders category, NORMAL priority
     - email, push
   * - Orders category, HIGH priority
     - email, sms, push

The category rule runs after the global rule at the same order. If an even
later rule removes email, that removal takes effect too. A user's optional
sms opt-out still suppresses sms; URGENT bypasses scheduling, not that opt-out.
If sms has no configured backend, no rule can enable it.

To stop all external channels for a matching rule, REMOVE all configured
channels. The rule's channels list itself cannot be empty, but the resulting
channel selection can be. This does not hide content in the in-app inbox.
