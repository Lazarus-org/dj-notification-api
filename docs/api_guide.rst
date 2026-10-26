REST API reference
===================

All examples use the mount point ``/notification/`` from :doc:`quick_start`.
If you mount the router elsewhere, replace that prefix. Endpoints use the
host project's DRF authentication classes and require an authenticated user.
There is no API for creating notifications or selecting another user's inbox.

Feeds, detail and counts
------------------------

.. list-table::
   :header-rows: 1
   :widths: 12 43 45

   * - Method
     - Path below /notification/
     - Result
   * - GET
     - notifications/
     - Unread, sent, active, personally undeleted items
   * - GET
     - activities/
     - Seen items with the same eligibility rules
   * - GET
     - notifications/{id}/
     - Detail of an item currently in the unread inbox
   * - GET
     - activities/{id}/
     - Detail of an item currently in the read activity list
   * - GET
     - notifications/{id}/preview/
     - Detail of a visible item whether read or unread; never marks seen
   * - GET
     - notifications/summary/
     - Counts across eligible read and unread items

Every query remains scoped to the current user. Staff/superuser status does
not expose another user's messages. A direct/group overlap produces one
item. Expired, cleared or otherwise inaccessible IDs return ``404``.

The default list representation contains ``id``, ``title``, ``description``,
``status``, ``link`` and ``timestamp``. It uses limit/offset pagination::

    GET /notification/notifications/?limit=20&offset=0&ordering=-timestamp

    {
      "count": 1,
      "next": null,
      "previous": null,
      "results": [
        {
          "id": 42,
          "title": "Example display title",
          "description": "Your order is ready.",
          "status": "INFO",
          "link": "https://app.example.com/orders/73",
          "timestamp": "2026-01-01T12:00:00Z"
        }
      ]
    }

This is an illustrative payload; IDs, timestamp formatting and human-readable
title depend on your data and DRF settings. Pagination defaults to 10 items,
caps ``limit`` at 100 and uses 10 when the limit is invalid or below one.
Follow ``next`` rather than constructing a fixed number of pages.

Detail and preview use the personal full representation: ``id``, ``title``,
``verb``, ``description``, ``status``, ``link``, ``is_sent``, ``public``,
``category``, ``priority`` and ``timestamp``. Recipient lists, groups,
other users' read states and arbitrary ``data`` are omitted. Configure list
representations in :doc:`settings` and :doc:`customization`.

Summary returns an unpaginated object::

    GET /notification/notifications/summary/

    {"total_count": 5, "read_count": 2, "unread_count": 3}

Read-only detail GET is the default. Once marked seen, an item's unread-detail
URL returns ``404``; use preview or activity detail to fetch it again.

Search, filters and ordering
----------------------------

Both feeds support:

* ``category=orders`` for one category slug. An unmatched slug gives no rows.
* ``priority=HIGH`` for LOW, NORMAL, HIGH or URGENT. Invalid values give ``400``.
* ``search=invoice`` using the configured search fields, initially
  ``verb`` and ``description``.
* ``ordering=-timestamp`` using configured fields, initially ``id``,
  ``timestamp`` and ``public``.

For example::

    GET /notification/notifications/?category=orders&priority=HIGH&search=invoice

Summary accepts category and priority filters too. Search and ordering are
list filter backends, not summary inputs. Filters cannot widen authorization.
Additional Django-filter fields require an explicitly configured filterset.

Single-item read actions
------------------------

Both actions accept an empty body and return ``200``::

    POST /notification/notifications/42/mark_seen/

    {"id": 42, "seen": true, "changed": true}

    POST /notification/notifications/42/mark_unseen/

    {"id": 42, "seen": false, "changed": true}

Repeating the same action returns ``changed: false``. Unlike unread detail,
these actions select from all eligible personal items, so marking an already
read item seen is valid. They cannot restore expired or cleared content.

Selected-item read actions
--------------------------

Send a JSON array in the ``ids`` field::

    POST /notification/notifications/bulk_mark_seen/
    Content-Type: application/json

    {"ids": [42, 43, 42]}

    {"processed": 2, "seen": true}

``bulk_mark_unseen/`` accepts the same body and returns ``seen: false``.
The request must contain 1–500 entries before deduplication, all valid
positive integer IDs. Repeated entries are deduplicated in request order.
A list with more than 500 entries is invalid even if many repeat.

The action is all-or-nothing. If any selected ID is inaccessible, the
response is ``404`` and no selected state changes are committed.
``processed`` counts unique eligible IDs, including ones already in the
requested state; it is not the number of newly inserted seen rows.

Mark everything read
---------------------

``POST notifications/mark_all_as_seen/`` processes the user's eligible unread
items and returns an object such as::

    {"detail": "3 Notifications marked as seen."}

This action operates on the whole eligible unread selection. Category,
search or priority parameters do not turn it into a filtered bulk action.
Use explicit IDs with ``bulk_mark_seen/`` for selected results. Concurrent
mark-all requests may report overlapping candidate counts while unique
constraints prevent duplicate read-state rows.

Clear read activities
----------------------

Soft clearing is enabled by default. Clear one seen item with::

    DELETE /notification/activities/42/

A successful response is ``204`` with no body. The compatibility path
``DELETE activities/42/clear_notification/`` has the same effect.
An unread item must be marked seen before it can be cleared as an activity.

For selected seen items::

    POST /notification/activities/bulk_clear/
    Content-Type: application/json

    {"ids": [42, 43]}

    {"processed": 2}

The same 1–500 input limit and atomic access validation apply.
``POST activities/clear_activities/`` clears all eligible seen items and
returns ``204``. These manager actions do not apply list query parameters.
There is no public undo endpoint. A second DELETE after clearing returns
``404`` because the activity is no longer accessible.

Category and channel preferences
---------------------------------

These collection endpoints are unpaginated:

* ``GET notifications/categories/`` returns active categories with
  ``category``, ``name`` and ``mandatory``.
* ``GET notifications/preferences/`` adds the user's effective ``enabled``.
* ``GET notifications/channel_preferences/`` returns active-category/channel
  combinations with ``category``, ``channel``, ``mandatory`` and ``enabled``.
  The catalog includes all four known channels, even when no provider is enabled.

Change a preference with PUT or PATCH::

    PATCH /notification/notifications/preferences/orders/
    Content-Type: application/json

    {"enabled": false}

    {"category": "orders", "name": "Orders", "mandatory": false, "enabled": false}

To disable only email for that category, use
``notifications/channel_preferences/orders/email/`` with the same body.
Missing overrides mean enabled. Setting ``true`` removes the override.
Unknown/inactive categories and unknown channels return ``404``; disabling
a mandatory category returns ``400``. No request accepts another user's ID.

A category opt-out can hide existing optional messages and prevent delivery.
A channel opt-out leaves the inbox intact. Opting back in can make existing
active inbox content visible again, but does not replay cancelled external
jobs. See :doc:`templates_and_channels`.

Delivery schedules
-------------------

``GET notifications/delivery_schedule/`` returns one effective record for
each known channel. Defaults are IMMEDIATE, UTC and no quiet hours::

    {
      "channel": "email",
      "frequency": "IMMEDIATE",
      "timezone": "UTC",
      "quiet_start": null,
      "quiet_end": null
    }

Update one channel through PUT or PATCH at
``notifications/delivery_schedule/email/``. PUT requires ``frequency``
and ``timezone`` and resets omitted quiet-hour values to null. PATCH keeps
omitted stored values, or starts from defaults when no schedule exists.
Only email supports DAILY/WEEKLY; other channels accept IMMEDIATE.
See :doc:`schedules_and_digests` for local-time behavior and retry effects.

Authentication, throttling and errors
--------------------------------------

The package uses the host's DRF authentication settings. Session-authenticated
unsafe requests must send a CSRF token. Do not add a user ID to a URL, body
or query string to impersonate the recipient.

Default request limits are 30/minute for ordinary authenticated users and
100/minute for staff. They use Django's cache through DRF throttling; configure
an appropriate shared cache for multiple processes. Staff's larger request
budget grants no extra content access.

.. list-table::
   :header-rows: 1

   * - Status
     - Meaning
     - Client handling
   * - 400
     - Invalid body, priority or preference/schedule input
     - Display field errors; correct input before retrying
   * - 401 / 403
     - Authentication, permission or CSRF failure
     - Reauthenticate or supply required credentials/CSRF token
   * - 404
     - Unknown ID or unavailable personal item
     - Remove stale client data and refresh feeds
   * - 405
     - Disabled operation or wrong HTTP method
     - Check enabled settings and use the documented method
   * - 429
     - Throttling
     - Respect Retry-After when supplied

The exact authentication status and error envelope depend on the project's
DRF classes. For example, an empty bulk list normally returns a field error
under ``ids``. Avoid treating every ``404`` as evidence that the notification
never existed: membership, expiry or clearing may have changed.

Permanent deletion and older clients
-------------------------------------

Permanent-delete REST actions are disabled by default. When explicitly
enabled, ``DELETE activities/delete_activities/`` and
``DELETE activities/{id}/delete_notification/`` require staff permission and
start from that administrator's own eligible seen activities. Deleting a
shared notification removes it for all recipients, not just the caller.

GET mutations are disabled by default. Older clients may opt into them through
the two switches in :doc:`upgrading`, but new clients should always use
explicit POST/DELETE actions. A legacy detail GET marks seen only when both
compatibility switches are enabled. Preview never writes state.
