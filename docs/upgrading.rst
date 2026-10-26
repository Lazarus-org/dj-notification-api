Upgrade an existing application
================================

Check the requirements and changelog for the exact release you plan to install.
Apply an upgrade first in an environment with a copy of your schema and
representative client flows.

Framework requirements
-----------------------

The documented source supports Python 3.10–3.14. Python 3.10/3.11 pair with
Django 5.2; Python 3.12+ can use Django 5.2, 6.0 or 6.1. DRF 3.18 is required.
Applications on Python 3.9 or Django 4.2/5.0/5.1 must upgrade their framework
environment before adopting these requirements.

Pin a published release compatible with your host application, install its
dependencies, then run::

    python manage.py migrate
    python manage.py check
    python manage.py showmigrations django_notification

Use Django's normal migration history; do not delete already-applied migration
records or replace historical migrations. Existing notifications retain
dynamic group behavior, the general category and normal priority; expiry is
unset unless your application configures it.

Move clients to explicit writes
--------------------------------

Detail GET is read-only by default. Replace implicit read marking with:

1. GET notifications/{id}/preview/ to display content.
2. POST notifications/{id}/mark_seen/ when the user actually reads it.
3. POST notifications/{id}/mark_unseen/ to undo read state.
4. DELETE activities/{id}/ to clear an eligible read item.

Use POST for mark_all_as_seen and clear_activities, and DELETE for explicitly
enabled permanent-delete actions. Session clients must supply a CSRF token
for unsafe methods. Detail on the unread endpoint returns 404 after reading;
preview or activity detail remains the appropriate read URL.

If older clients need a temporary transition, explicitly set::

    DJANGO_NOTIFICATION_API_ALLOW_LEGACY_GET_MUTATIONS = True
    DJANGO_NOTIFICATION_API_RETRIEVE_MARKS_SEEN = True

The first switch permits legacy GET actions. Both are required for automatic
seen-on-detail. These requests mutate state without normal session CSRF
protection and return deprecation/no-store headers. Migrate clients and return
both switches to False; cache headers do not make mutation GETs safe.

Review serializer and permission assumptions
---------------------------------------------

Personal endpoints remain recipient-scoped for staff/superusers. Move any
administrative cross-user browsing into a separately authorized administrative
interface rather than broadening personal querysets.

Full personal details do not contain all recipients, groups, other users'
seen records or arbitrary data. Update clients that previously depended on
those relationships. A custom list serializer still needs its own privacy
review; authentication alone does not make global relationships safe.

Use model-returning composable selectors for new code. Older projection
selectors remain available, while queryset mutation shims warn on use.
Move mutations to Notification.objects manager methods to retain event and
transaction behavior.

Enable integrations deliberately
---------------------------------

Migrations install queue/preference/template tables, but do not enable external
providers or sockets. For external delivery, configure outbox mode, backend
paths, receiver registration and both worker processes. For Channels, configure
ASGI authentication, origin checks, layer and adapter registration separately.

Ordinary ORM edits do not emit lifecycle events. Historic notifications are
not automatically backfilled when you enable a backend. Decide whether a
scoped backfill is necessary instead of replaying all old events indiscriminately.

Before switching traffic
-------------------------

Exercise an unread-to-read-to-cleared flow with an actual recipient and a
second unrelated account. Verify old clients no longer depend on mutating
GETs. If you enable external delivery, verify the configured destination,
one provider acceptance, retry behavior and failed-job recovery in your
environment. With WebSockets, reconnect and reconcile REST state.

Choose retention before pruning: permanent deletion cascades notification
state, delivery history and creation keys. Keep backups and use retention and
requeue dry runs to review the intended selection.
