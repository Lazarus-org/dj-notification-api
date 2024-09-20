Roles
=====
This section outlines the various roles within ``django-notification-api``, detailing their permissions, actions, and throttling limits for both API and admin interactions. By defining role-based access control, the system ensures secure and efficient management of notifications, while providing flexibility for different user levels. Whether for anonymous users with no access, authenticated users interacting via the API, or administrators managing the notification system, these roles offer a structured way to control who can create, retrieve, update, or delete notifications. This role-based framework helps maintain security, optimize performance, and support scalable system management.

API Roles
---------

This section defines the user roles that interact with the `dj-notification-api` and outlines their specific permissions, throttling limits, and actions available via the API. These roles allow for fine-grained control over who can create, retrieve, update, and delete notifications, and ensure that the system is scalable and secure for various levels of users.

1. Anonymous Users
~~~~~~~~~~~~~~~~~~
Anonymous users are those who are not authenticated within the Django application. By default, anonymous users do not have access to most of the features in the notification API.

**Permissions**:
  - **List Notifications**: ❌ (Disabled)
  - **Retrieve Notifications**: ❌ (Disabled)
  - **Create Notifications**: ❌ (Disabled)
  - **Delete/Modify Notifications**: ❌ (Disabled)

**Throttling**:
  - **Rate Limit**: N/A (No access)

**Use Case**:
  Anonymous users are generally restricted from interacting with the notification system.

2. Authenticated Users
~~~~~~~~~~~~~~~~~~~~~~
Authenticated users are regular users who have logged in to the Django application. They have basic permissions to view notifications.

**Permissions**:
  - **List Notifications**: ✅ (If ``DJANGO_NOTIFICATION_API_ALLOW_LIST`` is set to ``True``)
  - **Retrieve Notifications**: ✅ (If ``DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`` is set to ``True``)
  - **Create Notifications**: ❌ (Disabled by default)
  - **Delete/Modify Notifications**: ❌ (Disabled by default)

**Throttling**:
  - **Rate Limit**: ``30/minute`` (Configurable via ``DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE``)

**Use Case**:
  Authenticated users can view and retrieve their own notifications, but they cannot create or delete notifications unless explicitly allowed.

3. Staff Users (Admin)
~~~~~~~~~~~~~~~~~~~~~~
Staff users (admin or elevated users) have more privileges in terms of creating and managing notifications, depending on the configuration of the settings.

**Permissions**:
  - **List Notifications**: ✅ (If allowed by ``DJANGO_NOTIFICATION_API_ALLOW_LIST``)
  - **Retrieve Notifications**: ✅ (If allowed by ``DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE``)
  - **Create Notifications**: ❌
  - **Modify Notifications**: ❌
  - **Delete Notifications**: ✅ (If ``DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE`` is set to ``True``)

**Throttling**:
  - **Rate Limit**: ``100/minute`` (Configurable via ``DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE``)

**Use Case**:
  Staff users are responsible for maintaining the notification system. They can create, edit, and delete notifications for the user base.


Customizing Roles with Extra Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The system also allows for more fine-grained control through the ``DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS`` setting. You can define additional custom permission classes that extend the base permissions, adding conditions for API access. This is useful when specific user groups or roles require specialized access to certain notification features.

**Example**:
You can create a custom permission class to restrict access to only users with a particular role or attribute:

.. code-block:: python

    DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS = (
        "myapp.permissions.CustomPermissionClass"
    )

Role-Based Throttling
~~~~~~~~~~~~~~~~~~~~~
The package offers a **role-based throttling system**, allowing you to configure different API request rates for different user roles:

  - **Authenticated Users**: Throttled at a rate of ``30 requests/minute`` by default.
  - **Staff Users**: Throttled at a rate of ``100 requests/minute`` by default.
  - **Superusers**: No throttling applied.

This ensures that the API remains performant, and users with higher permissions are allowed to make more requests.

**Example Throttle Configuration**:

.. code-block:: python

    DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "30/minute"
    DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "100/minute"
    DJANGO_NOTIFICATION_API_THROTTLE_CLASS = (
        "django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"
    )

Summary of Role Capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Role
     - List Notifications
     - Retrieve Notifications
     - Create Notifications
     - Modify Notifications
     - Delete Notifications
     - Throttle Rate
   * - **Anonymous**
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - N/A
   * - **Authenticated**
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - 30/minute
   * - **Staff**
     - ✅
     - ✅
     - ✅ (Optional)
     - ❌
     - ✅ (Optional)
     - 100/minute

By configuring these roles, you ensure that each user type has access to the appropriate level of functionality within the notification API, maintaining security and system stability.

----

Admin Role
----------

This section outlines the role of admins in interacting with the `dj-notification-api` through the Django admin panel. Admin users have elevated privileges to manage notifications and their associated data.

1. Admin Users
~~~~~~~~~~~~~~
Admin users have comprehensive permissions to manage notifications, including creating, updating, deleting, and viewing both active and deleted notifications.

**Permissions**:
  - **Create Notifications**: ✅ (If ``DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION`` is set to ``True``)
  - **Modify Notifications**: ✅ (If ``DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION`` is set to ``True``)
  - **Delete Notifications**: ✅ (If ``DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION`` is set to ``True``)


**Use Case**:
  Admin users are responsible for maintaining the notification system, including marking notifications as sent, managing recipients, and tracking when notifications are seen.

Admin Actions
~~~~~~~~~~~~~
- **Mark as Sent**: Admins can mark selected notifications as sent, updating the ``is_sent`` field to ``True`` and receiving feedback on the number of notifications updated.

Inline Admin Interfaces
~~~~~~~~~~~~~~~~~~~~~~~
The admin panel includes two inline interfaces:
- **NotificationRecipientInline**: Manage recipients associated with notifications directly.
- **NotificationSeenInline**: View records of when notifications were seen by recipients.

List Display
~~~~~~~~~~~~
The list view for notifications includes fields such as:
- ``ID``: Unique identifier for each notification.
- ``Title``: Summary of the notification.
- ``Sent Status (is_sent)``: Indicates if the notification has been sent.
- ``Public Status``: Indicates if the notification is public.
- ``Timestamp``: Creation time of the notification.

Filtering
~~~~~~~~~
Admins can filter notifications by:
- ``is_sent``
- ``public``
- ``timestamp``

Search Functionality
~~~~~~~~~~~~~~~~~~~~
Search for notifications using:
- ``ID``
- ``Recipient Username Field``
- ``Group Name``

Pagination
~~~~~~~~~~
The admin list view displays **10 notifications per page** by default for better management of large lists.

Permissions Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~
Control admin permissions through settings:
- ``DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION``: Controls "add" action.
- ``DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION``: Controls "change" action.
- ``DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION``: Controls "delete" action.

Deleted Notifications
---------------------
Admin can manage deleted notifications with features like:

- **List Display** showing:
  - ``Notification ID``
  - ``Title``
  - ``Deleted by``
  - ``Deleted at``

- **List Filters** by ``deleted_at`` timestamp.
- **Pagination** showing **10 deleted notifications per page**.

Search Functionality for Deleted Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Search deleted notifications using:
- ``Notification ID``
- ``User Username Field``

Search Logic
~~~~~~~~~~~~
- **Notification ID Search**: Searches by ID if the term is a number.
- **Username Search**: Filters based on the username field if the term is a string.
