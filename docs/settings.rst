Configuration reference
=========================

Set these values in your Django project's settings module. The package loads
its API configuration during Django initialization; restart application and
worker processes after changing settings. Run ``python manage.py check``
before deployment to catch invalid types, import paths and delivery settings.

Only configure what you need. The inbox works with the defaults. Categories,
user preferences, schedules, templates and routing rules are database records,
not global settings.

HTTP behavior
--------------

.. list-table::
   :header-rows: 1
   :widths: 53 12 35

   * - Setting
     - Default
     - Effect
   * - DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE
     - True
     - Enables personal clearing of seen activities
   * - DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE
     - False
     - Enables staff-only permanent deletion actions
   * - DJANGO_NOTIFICATION_API_ALLOW_LIST
     - True
     - Enables list actions and notification summary
   * - DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE
     - True
     - Enables detail actions and notification preview
   * - DJANGO_NOTIFICATION_API_ALLOW_LEGACY_GET_MUTATIONS
     - False
     - Allows historical state-changing GET actions when explicitly enabled
   * - DJANGO_NOTIFICATION_API_RETRIEVE_MARKS_SEEN
     - False
     - Marks unread detail seen only if legacy GET mutations are also allowed

These switches do not grant recipient access. Disabling list/retrieve is not
a replacement for the host application's permission policy. See
:doc:`api_guide` for each route and :doc:`upgrading` for old HTTP clients.

Serializer selection
---------------------

``DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`` (bool, default False)
    Uses the personal full serializer for list responses when True. Detail
    and preview already use that serializer. It includes verb, category,
    priority and send/public flags; it does not expose recipients, group
    permissions, other users' seen state or arbitrary data.

``DJANGO_NOTIFICATION_SERIALIZER_FIELDS`` (list of strings or None, default None)
    Selects fields for the default dynamic list serializer. With None, lists
    use title plus id, description, status, link and timestamp. It does not
    change detail/preview representations. Explicit fields may expose sensitive
    model relations; choose only fields suitable for every addressed user.

``DJANGO_NOTIFICATION_SERIALIZER_CLASS`` (import path or None, default None)
    Custom list serializer. None selects NotificationDynamicSerializer. Full
    details takes precedence over this option. The configured class receives
    Notification model instances, not projected dictionaries.

``DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS`` (bool, default False)
    Removes None, empty strings, empty lists and empty dictionaries from
    built-in output. Despite its name, this filters more than null alone.
    Leave False when clients rely on a stable set of keys.

For a richer built-in list::

    DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS = True

For a deliberately narrow list, keep full details False and set::

    DJANGO_NOTIFICATION_SERIALIZER_FIELDS = [
        "id", "title", "description", "status", "category", "priority", "timestamp",
    ]

The configured projection/custom serializer affects lists, including activity
lists. It does not replace the protected personal detail serializer.
See :doc:`customization` for a complete application serializer.

Trusted user/group serialization
---------------------------------

These settings support nested serialization in trusted integrations using
``NotificationSerializer``. They do not add nested recipient relationships
to the built-in personal representation.

* ``DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS``: defaults to
  ``USERNAME_FIELD`` followed by the user model's ``REQUIRED_FIELDS``.
* ``DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS``: import path or None;
  None selects the package's UserSerializer.
* ``DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS``: import path or None;
  None selects the package's GroupSerializer.

Do not reuse a trusted serializer containing all recipients or seen users in
personal endpoints. A shared notification may involve unrelated accounts.

Authentication, permissions and parsers
---------------------------------------

Authentication comes from ``REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]``.
The package requires authenticated access and checks recipient visibility.
``DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS`` defaults to None and can
name one additional DRF permission class. It adds a restriction rather than
granting broader visibility.

``DJANGO_NOTIFICATION_API_PARSER_CLASSES`` defaults to import paths for
``rest_framework.parsers.JSONParser``, ``MultiPartParser`` and
``FormParser``. For JSON-only clients::

    DJANGO_NOTIFICATION_API_PARSER_CLASSES = [
        "rest_framework.parsers.JSONParser",
    ]

Supply serializer/permission/parser classes by dotted import path. Invalid
imports fail configuration; configure them before the application starts.

Throttling and pagination
--------------------------

``DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE``
    Default ``"30/minute"`` for ordinary authenticated users.

``DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE``
    Default ``"100/minute"``. Staff have the same recipient boundaries.

``DJANGO_NOTIFICATION_API_THROTTLE_CLASS``
    Default
    ``"django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"``.
    A custom import path replaces it; None leaves the view's inherited DRF
    throttling configuration in effect rather than adding this throttle.
    Use Django's shared cache when counters must span application processes.

``DJANGO_NOTIFICATION_API_PAGINATION_CLASS``
    Default
    ``"django_notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"``.
    Default page size is 10 and maximum is 100. A custom import path replaces
    it; None leaves inherited DRF pagination in effect. With no inherited
    paginator, lists return an array instead of a paginated envelope.

Example for different request budgets::

    DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "60/minute"
    DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "120/minute"

Ordering, search and filtersets
-------------------------------

* ``DJANGO_NOTIFICATION_API_ORDERING_FIELDS`` defaults to
  ``["id", "timestamp", "public"]``.
* ``DJANGO_NOTIFICATION_API_SEARCH_FIELDS`` defaults to
  ``["verb", "description"]``.
* ``DJANGO_NOTIFICATION_API_FILTERSET_CLASS`` defaults to None. To enable
  the bundled filterset, add ``django_filters`` to INSTALLED_APPS and set its
  import path as shown in :doc:`customization`.

Category/priority filtering is built in independently of the optional
filterset. Search is a text-search interface; avoid JSON fields or recipient
relations that leak information about other users. Keep the allowlist small
and index/order according to your application's query patterns.

Django admin
-------------

All three switches below default to False:

* ``DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION``
* ``DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION``
* ``DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION``

They control notification administration alongside Django model permissions.
Ordinary admin edits are ORM writes; they do not synthesize lifecycle events.
Use manager methods for notification creation and send transitions when
delivery/event integration matters.

``DJANGO_NOTIFICATION_ADMIN_SITE_CLASS`` defaults to None for Django's
default site. It accepts a dotted path to an AdminSite subclass (instantiated
once) or an existing AdminSite instance. Register related models on that site
when required by autocomplete widgets. Admin authorization is distinct from
personal REST access.

Events and external delivery
-----------------------------

``DJANGO_NOTIFICATION_API_EVENT_DELIVERY`` (str, default "signal")
    "signal" runs lifecycle callbacks after commit; "outbox" persists intent
    for a worker. External delivery requires "outbox". See :doc:`outbox`.

``DJANGO_NOTIFICATION_DELIVERY_BACKENDS`` (dict, default {})
    Maps enabled channel names (email, sms, push, webhook) to DeliveryBackend
    subclass import paths. An empty mapping enables no external channel.
    Configure receiver registration and workers too; a mapping alone does
    not send mail. See :doc:`delivery`.

``DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE`` (str, default LANGUAGE_CODE)
    Fallback language for message templates. Values such as en, fa and en-us
    are supported. Invalid deployment defaults fail system checks. User
    locale selection and fallback order are in :doc:`templates_and_channels`.

``DJANGO_NOTIFICATION_WEBHOOK_URL`` and ``DJANGO_NOTIFICATION_WEBHOOK_SECRET``
    Required only for SignedWebhookBackend. Supply an operator-controlled
    HTTPS URL and nonempty HMAC secret from your secret store/environment.
    The destination never comes from a notification's link or user input.

For a local email demonstration::

    DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"
    DJANGO_NOTIFICATION_DELIVERY_BACKENDS = {
        "email": "django_notification.delivery.backends.DjangoEmailBackend",
    }
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "notifications@example.com"

Production email configuration is Django's normal SMTP/backend configuration.
Secrets and provider credentials belong to the host application.

WebSockets
-----------

``DJANGO_NOTIFICATION_CHANNELS_DATABASE_ALIAS`` defaults to "default".
It chooses the database used for audience lookup and socket reauthorization.
Only events from that alias are dispatched by the adapter. Align it with the
database storing the notifications and with the outbox worker's
``--database`` argument.

Channel layers, ASGI authentication and origin validation use standard host
settings and middleware. Installing optional dependencies does not register
the adapter. Follow the complete setup in :doc:`channels`.
