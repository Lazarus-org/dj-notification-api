Notification behavior
======================

A notification represents application content addressed to an audience.
Reading, clearing and delivering that content are separate operations.
An order update addressed to two customers has one notification row, two
independent read states and, if email is configured, two email jobs.
Reading it in a browser does not mark an email as delivered.

Content and delivery state
---------------------------

``is_sent`` controls whether content is available to recipients. New
notifications default to ``False``. Set it to ``True`` at creation, or call
``Notification.objects.update_notification(id, is_sent=True)`` later.
It does not prove that an email was sent or a browser received anything.

``status`` describes the message: ``INFO``, ``SUCCESS``, ``WARNING``,
``ERROR``, ``CRITICAL``, ``SENSITIVE`` or ``INFRASTRUCTURE``.
``priority`` is separate: ``LOW``, ``NORMAL``, ``HIGH`` or
``URGENT``. Neither value is a read-state flag or delivery job status.

.. list-table:: Independent state
   :header-rows: 1

   * - State
     - Scope
     - Effect
   * - Sent / unsent
     - Notification
     - Makes content available / unavailable to personal feeds
   * - Seen / unseen
     - Notification and user
     - Selects activity list / unread inbox
   * - Cleared
     - Notification and user
     - Removes the item from that user's feeds
   * - Expired
     - Notification
     - Removes access at the expiration instant
   * - Delivery status
     - Notification, user and external channel
     - Tracks worker/provider progress independently of reading

Choosing an audience
---------------------

Direct recipients and group recipients are combined with OR. A user targeted
both ways sees one item. Staff and superuser flags do not bypass targeting.
The ``public`` field is metadata; ``True`` does not broadcast the notification
or permit unauthenticated access.

Use ``DYNAMIC`` groups for information that should follow current access,
such as a team work queue. A member joining later can see earlier active
group notifications; a member leaving loses access unless directly targeted.

Use ``SNAPSHOT`` for announcements addressed to the people present at
creation. The manager copies group members into direct recipient rows in the
creation transaction. Later members do not gain access, and leaving does not
revoke copied recipients. The user model needs a ``groups`` many-to-many
relation to Django's ``auth.Group`` for group snapshots. Direct-only
notifications do not require that relation. See :doc:`usage` for examples.

Personal feed eligibility
--------------------------

A notification appears in a personal feed only when these conditions hold:

1. The user is persisted, authenticated and active.
2. The user is a direct recipient or eligible group recipient.
3. The notification is sent and has not expired.
4. The user has not cleared it.
5. The user has not disabled its optional category.

The unread inbox then requires no seen record for that user; the activity
list requires a seen record. Summary counts cover both sets. Marking an item
unseen moves it back to the inbox. Clearing does not delete it for other
recipients. Permanent deletion removes shared content and state for everyone.

An inaccessible ID returns ``404``. Custom queries must compose the selectors
in :doc:`usage`; ``visible_to(user)`` checks audience and category preference,
not every feed condition.

Categories and preferences
---------------------------

Categories are managed records with stable slug keys, such as ``orders`` or
``security``. Migrations create ``general`` for applications without their
own catalog. Creation requires an active category.

A category preference affects personal visibility and external eligibility.
A channel preference affects one external channel in a category. Disabling
``orders/email`` leaves the update visible in the inbox and eligible for other
configured channels. Missing preference rows mean enabled.

Mandatory categories ignore opt-outs. Mandatory categories and ``URGENT``
notifications bypass quiet hours and digests; only mandatory categories
bypass preference opt-outs. Neither overrides authorization or expiration.
Routing can still restrict the external channels used.

Expiration and retention
-------------------------

``expires_at=None`` means no expiration. Otherwise, the item is expired at
the exact configured instant, including for people who previously read it.
Expiry hides content and cancels ineligible pending delivery; it does not
erase records. :doc:`operations` explains explicit retention cleanup.

What an acknowledgement means
-------------------------------

Default signal callbacks run after commit in the current process. A crash can
lose a callback. Outbox mode stores event intent in the mutation transaction
and lets a worker retry it.

An outbox event marked ``DELIVERED`` means registered receivers completed.
A delivery job marked ``DELIVERED`` means the provider adapter accepted the
send. A WebSocket hint asks the client to refresh REST data. None proves a
person read the message.

If a provider accepts a request and the worker crashes before recording
success, retrying can repeat the effect. Pass the adapter's stable idempotency
key to providers that support it. SMTP cannot guarantee deduplication.
See :doc:`outbox` for receiver replay and :doc:`delivery` for provider retries.
