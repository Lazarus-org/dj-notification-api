Settings
=========

This section outlines the available settings for configuring the `dj-notification-api` package. You can customize these settings in your Django project's `settings.py` file to tailor the behavior of the notification system to your needs.

Example Settings
----------------

Below is an example configuration with default values:

.. code-block:: python

    DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE = True
    DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE = False
    DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION = False
    DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION = False
    DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION = False
    DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = None
    DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS = False
    DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS = False
    DJANGO_NOTIFICATION_API_ALLOW_LIST = True
    DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE = True
    DJANGO_NOTIFICATION_SERIALIZER_FIELDS = None  # if you want to have your custom fields, you need to pass this as a list of fields
    DJANGO_NOTIFICATION_SERIALIZER_CLASS = (
        None  # pass your custom notification serializer if needed
    )
    # DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS = [if not provided, gets USERNAME_FIELD and REQUIRED_FIELDS from user model]
    DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS = (
        "django_notification.api.serializers.UserSerializer"
    )
    DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS = (
        "django_notification.api.serializers.group.GroupSerializer"
    )
    DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "30/minute"
    DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "100/minute"
    DJANGO_NOTIFICATION_API_THROTTLE_CLASS = (
        "django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"
    )
    DJANGO_NOTIFICATION_API_PAGINATION_CLASS = "django_notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"
    DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS = None
    DJANGO_NOTIFICATION_API_PARSER_CLASSES = [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ]
    DJANGO_NOTIFICATION_API_FILTERSET_CLASS = None
    DJANGO_NOTIFICATION_API_ORDERING_FIELDS = ["id", "timestamp", "public"]
    DJANGO_NOTIFICATION_API_SEARCH_FIELDS = ["verb", "description"]

Settings Overview
--------------------

Below is a detailed description of each setting, so you can better understand and tweak them to fit your project's needs.

``DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``True``

**Description**: Enables soft delete, allowing notifications to be excluded from API views without removing them from the database. If enabled, the ``clear_activities`` and ``clear_notification`` actions will be available in the ``activities`` API.

----

``DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: Enables hard delete, allowing notifications to be permanently removed from the database. If enabled, the ``delete_activities`` and ``delete_notification`` actions will be available in the ``activities`` API.

----

``DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: Controls whether the admin interface allows adding new notifications. Set this to ``True`` to enable Admin users to create new notifications.


----

``DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: Controls whether the admin interface allows modifying existing notifications. Set this to ``True`` to allow Admin users to edit notifications.

----

``DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: Controls whether the admin interface allows deleting notifications. Set this to ``True`` to enable Admin users to delete notifications.

----

``DJANGO_NOTIFICATION_ADMIN_SITE_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``Optional[str]``

**Default**: ``None``

**Description**: Optionally specifies A custom AdminSite class to apply on Admin interface. This allows for more customization on Admin interface, enabling you to apply your AdminSite class into `dj-notification-api` Admin interface.

----

``DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: When set to ``True``, API responses will include all notification fields. By default, only essential fields are returned.

----

``DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``False``

**Description**: When set to ``True``, API responses will exclude any fields that it's value is ``null``.

----

``DJANGO_NOTIFICATION_API_ALLOW_LIST``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``True``

**Description**: Allows the listing of notifications via the API. Set to ``False`` to disable this feature.

----

``DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``bool``

**Default**: ``True``

**Description**: Allows retrieving individual notifications via the API. Set to ``False`` to disable this feature.

----

``DJANGO_NOTIFICATION_SERIALIZER_FIELDS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Type**: ``List[str]``

**Default**: ``["id", "description", "status", "link", "timestamp"]``

**Description**: Defines the fields to be included in the notification dynamic serializer in API.

**Note**: Note: By default, the related setting is set to ``None`` and use default fields, which means the queryset will use ``.values()`` to fetch only the default fields. However, if you add custom fields, the actual queryset will be returned without using ``.values()``.

----

``DJANGO_NOTIFICATION_SERIALIZER_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Type**: ``str``

**Default**: ``"django_notification.api.serializers.dynamic_notification.NotificationDynamicSerializer"``

**Description**: Specifies the serializer class used for notification objects in the API. Customize this if you need a different notification serializer.

**Example**:

.. code-block:: python

    from rest_framework.serializers import ModelSerializer

    from django_notification.models.notification import Notification


    class CustomNotificationSerializer(ModelSerializer):

        group = YourGroupSerializer(many=True, read_only=True)
        recipient = YourUserSerializer(many=True, read_only=True)
        seen_by = YourUserSerializer(many=True, read_only=True)

        class Meta:
            model = Notification
            fields = (
                "id",
                "recipient",
                "group",
                "verb",
                "status",
                "actor_content_type",
                "target_content_type",
                "action_object_content_type",
                "link",
                "is_sent",
                "seen_by",
                "public",
                "data",
                "timestamp",
            )

**Note**: You can define a custom serializer for regular users like this, while staff users will continue to receive the default detailed serializer. This allows for tailored data representation based on user roles.

----

``DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``List[str]``

**Default**: ``USERNAME_FIELD`` and ``REQUIRED_FIELDS`` from user model

**Description**: Defines the fields to be included in the user serializer in API.

----

``DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``str``

**Default**: ``"django_notification.api.serializers.UserSerializer"``

**Description**: Specifies the serializer class used for user objects in the API. Customize this if you need a different user serializer.

----

``DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``str``

**Default**: ``"django_notification.api.serializers.group.GroupSerializer"``

**Description**: Specifies the serializer class used for group objects in the API. You can change this to use a different group serializer.

----

``DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``str``

**Default**: ``"30/minute"``

**Description**: Sets the throttle rate (requests per minute, hour or day) for authenticated users in the API.

----

``DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: `str`

**Default**: `"100/minute"`

**Description**: Sets the throttle rate (requests per minute, hour or day) for staff (Admin) users in the API.

----

``DJANGO_NOTIFICATION_API_THROTTLE_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``str``

**Default**: ``"django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"``

**Description**: Specifies the throttle class used to limit API requests. Customize this or set it to ``None`` if no throttling is needed or want to use ``rest_framework`` `DEFAULT_THROTTLE_CLASSES`.

----

``DJANGO_NOTIFICATION_API_PAGINATION_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``str``

**Default**: ``"django_notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"``

**Description**: Defines the pagination class used in the API. Customize this if you prefer a different pagination style or set to ``None`` to disable pagination.

----

``DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``Optional[str]``

**Default**: ``None``

**Description**: Optionally specifies an additional permission class to extend the base permission (``IsAuthenticated``) for the API. This allows for more fine-grained access control, enabling you to restrict API access to users with a specific permission, in addition to requiring authentication.

----

``DJANGO_NOTIFICATION_API_PARSER_CLASSES``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``List[str]``

**Default**:
  .. code-block:: python

    DJANGO_NOTIFICATION_API_PARSER_CLASSES = [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ]

**Description**: Specifies the parsers used to handle API request data formats. You can modify this list to add your parsers or set ``None`` if no parser needed.

----

``DJANGO_NOTIFICATION_API_FILTERSET_CLASS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``Optional[str]``

**Default**: ``None``

**Description**: Specifies the filter class for API queries. If you want to use this, you need to add ``django_filters`` to your `INSTALLED_APPS` and provide the path to the ``NotificationFilter`` class (``"django_notification.api.filters.notification_filter.NotificationFilter"``). Alternatively, you can use a custom filter class if needed.

in your settings.py:

.. code-block:: python

  INSTALLED_APPS = [
      # ...
      "django_filters",
      # ...
  ]

and then apply this setting:

.. code-block:: python

  # apply in settings.py

  DJANGO_NOTIFICATION_API_FILTERSET_CLASS = (
      "django_notification.api.filters.notification_filter.NotificationFilter"
  )


``DJANGO_NOTIFICATION_API_ORDERING_FIELDS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``List[str]``

**Default**: ``["id", "timestamp", "public"]``

**Description**: Specifies the fields available for ordering in API queries, allowing the API responses to be sorted by these fields. you can see all available fields here

----

``DJANGO_NOTIFICATION_API_SEARCH_FIELDS``:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
**Type**: ``List[str]``

**Default**: ``["verb", "description"]``

**Description**: Specifies the fields that are searchable in the API, allowing users to filter results based on these fields.

----

All Available Fields:
---------------------

These are all fields that are available for searching, ordering, and filtering in the notifications API with their recommended usage:


- ``id``: Unique identifier of the notification (orderable, filterable).
- ``recipient``: The users receiving the notification (filterable).
- ``group``: The groups receiving the notification (filterable).
- ``verb``: The action associated with the notification (searchable).
- ``description``: A description of the notification (searchable).
- ``status``: Current status of the notification (filterable).
- ``actor_content_type``: Content type of the actor object (filterable).
- ``target_content_type``: Content type of the target object (filterable).
- ``action_object_content_type``: Content type of the action object (filterable).
- ``public``: Indicates if the notification is public (orderable, filterable).
- ``timestamp``: The time when the notification was created (orderable, filterable).
- ``link``: URL associated with the action (searchable).
- ``data``: Additional metadata or attributes in JSON format (searchable).
- ``seen_by``: Users who have seen the notification (filterable).

**Note**: Exercise caution when modifying search and ordering fields. **Avoid** using foreign key or joined fields (``recipient``, ``group``, ``all content_types``, ``seen_by``) in **search fields**, as this may result in errors. instead you can access the inner fields of them like this: ``recipient__username``.
