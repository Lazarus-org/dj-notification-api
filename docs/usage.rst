Creating and managing notifications
====================================

Use the notification manager for lifecycle changes and composable querysets
for selection. The examples assume persisted ``actor`` and ``recipient``
users. Applications decide who may create, retarget or permanently delete
content; the manager is a trusted application API, not a public authorization
boundary for arbitrary requests.

Create an application notification
------------------------------------

Create the category before using its slug::

    from datetime import timedelta
    from django.utils import timezone
    from django_notification.models import Notification, NotificationCategory

    NotificationCategory.objects.get_or_create(
        slug="orders", defaults={"name": "Order updates"},
    )

    notification = Notification.objects.create_notification(
        actor=actor,
        recipients=[recipient],
        verb="confirmed your order",
        description="Order 73 is ready for collection.",
        category="orders",
        priority="NORMAL",
        status="SUCCESS",
        link="https://app.example.com/orders/73",
        is_sent=True,
        expires_at=timezone.now() + timedelta(days=7),
        data={"order_reference": "73"},
    )

The default category is ``general``, default priority NORMAL, default status
INFO and default send state False. Categories must exist and be active.
``data`` is application metadata and is not included in built-in personal
detail output. Do not assume metadata is safe to expose through a custom
serializer.

``actor``, ``target`` and ``action_object`` are generic model references.
Use actor for the initiator, target for the object affected, and action_object
when another object is part of the action. Their generic object ID columns
use positive integers; UUID/string object identities are not supported by
these existing columns. Related objects must be saved before keyed creation.

Creating a notification and attaching its recipients/groups is atomic.
Wrap the call with your business writes in an outer ``transaction.atomic()``
on the same database when they must commit together. Default signal callbacks
wait for the outer commit. Outbox mode persists intent in that transaction.

Choose direct or group recipients
----------------------------------

Direct recipients can be a saved user, a collection of users or a queryset.
Group targets are Django ``auth.Group`` objects. Both dimensions may be used::

    notification = Notification.objects.create_notification(
        actor=actor,
        verb="published a team announcement",
        recipients=[recipient],
        groups=[team],
        group_audience_mode="DYNAMIC",
        is_sent=True,
    )

DYNAMIC is the default: current members gain access, and departing members
lose it unless directly targeted. Snapshot the creation-time members instead
when historical membership should define the audience::

    frozen = Notification.objects.create_notification(
        actor=actor,
        verb="published the monthly statement",
        groups=[team],
        group_audience_mode="SNAPSHOT",
        is_sent=True,
    )

Snapshot creation writes group members to direct recipient rows, preserving
explicit recipients and deduplicating overlap. Later membership changes do
not change that audience. Adding a group afterward with ordinary ORM methods
does not populate a snapshot. Treat the audience policy and frozen recipients
as immutable unless your application implements a deliberate retargeting
operation. Concurrent membership edits do not guarantee a globally serialized
membership cutoff.

Send a draft
-------------

A draft is stored but absent from personal feeds and external delivery::

    draft = Notification.objects.create_notification(
        actor=actor,
        recipients=[recipient],
        verb="prepared an account update",
    )
    assert draft.is_sent is False

    sent = Notification.objects.update_notification(draft.pk, is_sent=True)

``update_notification()`` supports ``is_sent``, ``public`` and ``data``;
None means leave the field unchanged. It returns the notification, emits an
updated event only for changed values, and emits a sent event for the
unsent-to-sent transition. It is not an arbitrary content-edit API.

Send eligible drafts for explicit targets with
``Notification.objects.mark_all_as_sent(recipients=[recipient])``. With no
recipient/group constraints it selects all active drafts, so call it only
from appropriately authorized application code. The operation uses bounded
ID pages in one transaction and emits an individual sent event per change.
Event-based delivery does not observe plain ``.update(is_sent=True)``.

Compose a personal query
------------------------

Use model-returning selectors for application views::

    personal = (
        Notification.objects.visible_to(recipient)
        .active_at()
        .sent_only()
        .not_deleted_by(recipient)
    )
    unread = personal.unseen_by(recipient).order_by("-timestamp", "-pk")
    read = personal.seen_by(recipient)
    urgent_orders = unread.in_category("orders").with_priority("URGENT")

``visible_to()`` checks direct/group audience and optional-category preferences.
It does not imply sent, active or undeleted, so retain the other selectors.
Use ``active_at(when)`` and ``expired_at(when)`` with a shared timestamp when
you need a consistent expiry boundary across related queries.

``with_related()`` prefetches recipient, group, group permissions and seen
relations for trusted serializers that traverse them. The built-in personal
representation avoids those relations. Extra prefetching is unnecessary for
a compact personal list.

Read and clear per user
-----------------------

The manager validates personal eligibility for read-state operations::

    changed = Notification.objects.set_seen(recipient, notification.pk, seen=True)
    assert changed is True
    assert Notification.objects.set_seen(recipient, notification.pk, seen=True) is False

    Notification.objects.set_many_seen(
        recipient, [notification.pk], seen=False,
    )
    Notification.objects.mark_all_as_seen(recipient)
    Notification.objects.clear_selected(recipient, [notification.pk])

``set_seen()`` returns whether state changed; ``set_many_seen()`` returns the
number of unique eligible IDs. Selected operations require 1–500 IDs and are
atomic: an inaccessible ID causes Http404 and no selected changes commit.
Clearing requires seen content. ``clear_all(user)`` clears that user's
eligible seen items; it returns None.

Bulk mark-all/clear-all writes use 500-item pages within one transaction.
Counts represent eligible candidates, so concurrent callers can report
overlapping counts without storing duplicate state rows. Clearing leaves
other recipients' state intact. There is no personal REST restore action.

Retry creation with an idempotency key
--------------------------------------

Use an idempotency key for one logical event, such as an order confirmation::

    def order_confirmation(actor, customer, order_id):
        return Notification.objects.create_notification(
            actor=actor,
            recipients=[customer],
            verb="confirmed your order",
            category="orders",
            is_sent=True,
            idempotency_key=f"shop:order:{order_id}:confirmed",
        )

An identical retry returns the original row and does not reset its read state,
audience, content or expiry. Reusing the key with different arguments raises
ValueError. Recipient/group order and duplicates do not change the request
fingerprint. Category, priority, actor/related identities, content, explicit
audience and expiration do participate.

Keys are namespaced by creation mode, not automatically by user. Choose a
server-controlled application/event namespace. A user-supplied string without
scope can collide with another caller. Keys must be nonblank, unpadded text
of at most 200 characters. Hard deletion removes associated key claims, so
a later retry can create a new notification.

Coalesce a burst with deduplication
------------------------------------

Use a fixed window when repeated observations should share one inbox item::

    alert = Notification.objects.create_notification(
        actor=actor,
        recipients=[recipient],
        verb="detected repeated login failures",
        description="Review recent sign-in attempts.",
        is_sent=True,
        deduplication_key=f"security:login-failures:{recipient.pk}",
        deduplication_window=timedelta(minutes=5),
    )

Within the original five-minute window, repeated calls return the same row
even when content changes. They do not update that row or extend the window.
Changing actor, related objects, category, priority or intended audience
within the window raises ValueError. After the window expires, a new
notification is created and the claim points to it.

An expired notification is not reused by deduplication. Idempotency retries
still return their original row even after expiry while it exists.
Use one key mode per call; a deduplication window must be a positive timedelta.
Expired deduplication claims are not automatically pruned as standalone rows.

Expiration and permanent deletion
----------------------------------

``expires_at`` accepts None, an aware datetime with USE_TZ=True, or a naive
datetime with USE_TZ=False. At the exact expiry instant, personal access ends;
state remains stored until cleanup. Extending or changing content through
ordinary ORM writes does not emit lifecycle events.

The retention command defaults to a dry run and a 30-day delay after expiry::

    python manage.py prune_expired_notifications
    python manage.py prune_expired_notifications --execute --older-than-days=30

Deletion cascades to recipient/read/deletion state, creation keys and delivery
records. The retention command operates in separate bounded transactions,
not one transaction for the entire run. See :doc:`operations` before applying
retention to data used by analytics or retry/replay policies.

Trusted code can call
``Notification.objects.delete_notification(id, soft_delete=False)`` for
permanent deletion. This removes shared content for every recipient.
Authorize that operation in your application; it is not a per-user clear.

Database aliases and older interfaces
--------------------------------------

Use ``Notification.objects.db_manager("notifications")`` for manager
mutations on a non-default database. Put business writes, notification rows
and outbox intent on the same transaction/database when atomicity is required.
Configure the matching alias for workers and any Channels adapter.

Older selectors ``all_notifications()``, ``sent()``, ``unsent()``,
``seen()`` and ``unseen()`` remain available. Their ``display_detail=False``
path can return dictionary projections; model-returning composable selectors
are preferable for new integrations. Queryset mutation shims emit
DeprecationWarning; use manager methods instead.

Direct ORM save/update/delete, ordinary admin edits and retention cleanup do
not capture lifecycle events automatically. Use the manager mutation paths
when a state change must reach :doc:`events`, :doc:`outbox` or :doc:`delivery`.
