Permissions and audience visibility
===================================

The personal REST API and the Django admin are **different permission
surfaces**. Staff status does not imply access to every user's notification
in the personal REST API.

Personal REST API
-----------------

* **Anonymous clients:** no personal inbox or preference access.
* **Authenticated clients:** read and change the state of their **own** visible
  notifications; manage their **own** category, channel and schedule settings.
* **Staff and superusers:** the same personal audience checks apply to inbox,
  activity, preview and preferences. Staff status alone does **not** bypass
  direct/group targeting, expiration, personal deletion or category choices.
* **Hard deletion:** only if enabled with
  ``DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE=True``, with ``IsAdminUser``
  on the action, and still restricted to the admin's personal activities.

A personal notification is available only when all relevant conditions hold:
it is sent, not expired, visible to the current recipient, not soft-deleted
for them, and not excluded by an applicable optional category preference.

Groups
------

Notifications can target recipients and/or Django ``Group`` objects.
Recipients match by **direct user OR group membership**, not both.

* ``DYNAMIC`` (default): group membership is evaluated at query/send time.
  Leaving a group removes access unless the user is also a direct recipient.
* ``SNAPSHOT``: group members are materialized into direct recipient records
  when the notification is created. Later membership changes do not alter
  that frozen audience.

In both cases, membership in multiple target groups does not duplicate an
inbox item. Anonymous, inactive, and unsaved users are not eligible for
personal notification operations. See :doc:`usage` for queryset details.

Read and delete state
---------------------

Read state and soft-deletion state are per user. Marking a group notification
seen or clearing it does not mark or clear it for other members. The API
requires all selected bulk targets to be eligible before mutating any of them.

Administrative interface
------------------------

Django admin access follows Django model permissions and the package's
admin configuration. Admin features may expose management operations not
available in the personal API. Do not treat a custom administrative serializer
or queryset as a substitute for recipient-safe personal access.

Throttling and host policy
--------------------------

The package defaults to a role-based throttle policy with rate strings
``30/minute`` for authenticated users and ``100/minute`` for staff. Hosts
may change throttling, authentication, parsers, serializer classes, and extra
permission settings. Permission and rate settings are described in
:doc:`settings`. Keep any custom authorization at least as restrictive as
the package's audience constraints.
