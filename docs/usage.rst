Usage
=====

This section provides a comprehensive guide on how to utilize the package's key features, including the functionality of the Django admin panels for managing notifications and deleted notifications, and Manager methods for handling notifications.

Admin Site
----------

If you are using a **custom admin site** in your project, you must pass your custom admin site configuration in your Django settings. Otherwise, Django may raise the following error during checks:

.. code-block:: shell

  ERRORS:
  <class 'django_notification.admin.deleted_notification.DeletedNotificationAdmin'>:
   (admin.E039) An admin for model "User" has to be registered to be referenced by DeletedNotificationAdmin.autocomplete_fields.


To resolve this, In your ``settings.py``, add the following setting to specify the path to your custom admin site class instance

.. code-block:: python

  DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = "path.to.your.custom.site"

example of a custom Admin Site:
.. code-block:: python

  from django.contrib.admin import AdminSite


  class CustomAdminSite(AdminSite):
      site_header = "Custom Admin"
      site_title = "Custom Admin Portal"
      index_title = "Welcome to the Custom Admin Portal"


  # Instantiate the custom admin site as example
  example_admin_site = CustomAdminSite(name="custom_admin")

and then reference the instance like this:

.. code-block:: python

  DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = "path.to.example_admin_site"

This setup allows `dj-notification-api` to use your custom admin site for it's Admin interface, preventing any errors and ensuring a smooth integration with the custom admin interface.

Notifications Admin Panel
-------------------------

The ``NotificationAdmin`` class provides a comprehensive admin interface for managing notifications in the Django admin panel. The features and functionality are described below:

Admin Actions
~~~~~~~~~~~~~

- **Mark as Sent**:

  An admin action that allows you to mark selected notifications as sent. When this action is performed, the ``is_sent`` field of the selected notifications will be updated to ``True``. After execution, the admin will receive feedback indicating how many notifications were successfully updated.

Inline Admin Interfaces
~~~~~~~~~~~~~~~~~~~~~~~

The ``NotificationAdmin`` panel includes two inline admin interfaces that allow admins to view and manage related models directly from the notification page:

- ``NotificationRecipientInline``:

  Displays and manages the recipients associated with each notification. Admins can view or add recipient information directly within the notification details page.

- ``NotificationSeenInline``:

  Displays and manages the records of when notifications were seen by recipients. This provides visibility into which recipients have already viewed the notification.

List Display
~~~~~~~~~~~~

The list view for notifications includes the following fields:

- ``ID``: The unique identifier for each notification.
- ``Title``: The notification title or a summary.
- Sent Status (``is_sent``): Indicates whether the notification has been sent.
- ``Public`` Status: Indicates if the notification is public.
- ``Timestamp``: The time when the notification was created.

This view helps admins get a quick overview of the notifications and their current status.

Filtering
~~~~~~~~~

Admins can filter the list of notifications based on the following fields:

- ``is_sent``: Filter by whether the notification has been sent or not.
- ``public``: Filter by whether the notification is public or private.
- ``timestamp``: Filter by the creation time of the notification.

These filters make it easier to find specific notifications or groups of notifications based on status or time.

Search Functionality
~~~~~~~~~~~~~~~~~~~~

Admins can search for notifications using the following fields:

- ``ID``: The unique identifier of the notification.
- ``Recipient Username``: The username of the recipient associated with the notification.
- ``Group Name``: The name of the group associated with the notification.

This search functionality enables quick access to specific notifications by key identifiers.

Pagination
~~~~~~~~~~

The admin list view displays **10 notifications per page** by default. This can help improve load times and make it easier for admins to manage large lists of notifications.

Permissions Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

The admin permissions for ``add``, ``change``, and ``delete`` actions can be controlled through the following Django settings:

- ``DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION``: Controls whether the "add" action is available in the Notifications and Deleted Notifications Admin. Defaults to ``False``.

- ``DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION``: Controls whether the "change" action is allowed in the Notifications and Deleted Notifications Admin. Defaults to ``False``.

- ``DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION``: Controls whether the "delete" action is available in the Notifications and Deleted Notifications Admin. Defaults to ``False``.

----

Deleted Notifications Admin Panel
---------------------------------

The Deleted Notifications Admin interface allows admins to manage notifications that have been marked as deleted. Admins can view, filter, and search through deleted notifications to ensure better tracking and management.

Key Features
~~~~~~~~~~~~

- **Autocomplete Fields**:

  - Autocomplete is available for the ``notification`` and ``user`` fields to facilitate quick selection.

- **List Display**:

  The admin interface shows the following fields in the list view:

  - ``Notification ID``: The ID of the deleted notification.
  - ``Title``: The title of the deleted notification.
  - ``Deleted by``: The username of the user who deleted the notification.
  - ``Deleted at``: The timestamp indicating when the notification was deleted.

- **List Filters**:

  - The admin interface allows filtering by the ``deleted_at`` timestamp, making it easy to view notifications deleted within specific time periods.

- **Pagination**:

  - By default, the list view displays **10 deleted notifications per page**, improving the performance of the admin interface when dealing with large numbers of entries.

Search Functionality
~~~~~~~~~~~~~~~~~~~~

Admins can search for deleted notifications using the following fields:

- ``Notification ID``: Search by the unique identifier of the deleted notification.
- ``Username``: Search by the username of the user who deleted the notification.

Search Logic
~~~~~~~~~~~~

Users can do the searching based on this functionality:

- **Notification ID Search**: If the search term is a number, searches by the notification ID.
- **Username Search**: If the search term is a string, filters based on the username of the user who deleted the notification.

----

NotificationDataAccessLayer (Manager)
-------------------------------------

The ``django_notification`` provides a Manager Class with various methods to interact with notifications in different contexts. Users typically use `Notification.objects.create_notification()` to create notifications, but other methods are available for querying and managing notifications. Below is an overview of the available methods:


Return All Notifications
~~~~~~~~~~~~~~~~~~~~~~~~

The ``all_notifications`` method retrieves all notifications that have not been deleted. It provides filtering options based on recipients and groups, and can return simplified details if specified.

**Method Signature**

.. code-block:: python

    from django_notification.models.notification import Notification

    Notification.objects.all_notifications(recipients, groups, display_detail)

**Arguments:**

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
  Optional filter for notifications based on recipients. Can be:

  - A single ``UserModel`` instance.
  - A ``QuerySet`` of ``UserModel`` instances.
  - A list of ``UserModel`` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
  Optional filter for notifications based on groups. Can be:

  - A single ``Group`` instance.
  - A ``QuerySet`` of ``Group`` instances.
  - A list of ``Group`` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (``Optional[bool]``):
  Indicates whether to return simplified details.

  - If ``True``, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If ``False``, the method returns a ``QuerySet`` of notification instances.

**Returns:**

- A ``QuerySet`` of notifications, or a dictionary of simplified details if ``display_detail`` is ``True``.

**Example Usage:**

To retrieve all notifications for a specific user:

.. code-block:: python

    from django_notification.models.notification import Notification

    notifications = Notification.objects.all_notifications(
        recipients=user_instance, display_detail=True
    )


Return All Sent Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``sent`` method retrieves all sent notifications, excluding those that have been soft-deleted by the specified user. It allows filtering based on recipients, groups, and additional conditions.

**Method Signature**

.. code-block:: shell

    from django_notification.models.notification import Notification

    Notification.objects.sent(
        recipients,
        exclude_deleted_by,
        groups,
        display_detail,
        conditions,
    ) -> QuerySet

**Arguments:**

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
  Optional filter for notifications based on recipients. Can be:

  - A single ``UserModel`` instance.
  - A ``QuerySet`` of ``UserModel`` instances.
  - A list of ``UserModel`` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **exclude_deleted_by** (``Optional[UserModel]``):
  Optional filter to exclude notifications that have been soft-deleted by a specific user. If provided, the method excludes all notifications that have been marked as deleted by this user.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
  Optional filter for notifications based on groups. Can be:

  - A single ``Group`` instance.
  - A ``QuerySet`` of ``Group`` instances.
  - A list of ``Group`` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (``Optional[bool]``):
  Indicates whether to return simplified details.

  - If ``True``, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If ``False``, the method returns a ``QuerySet`` of notification instances.

- **conditions** (``Optional[Q]``):
  Additional filter conditions. Accepts a ``Q`` object from ``django.db.models`` for specifying extra conditions that may be needed for various contexts. Defaults to ``Q()`` (no additional conditions).

**Returns:**

- A `QuerySet` of notifications, or a dictionary of simplified details if `display_detail` is `True`.

**Example Usage:**

To retrieve all sent notifications for a specific user, excluding those deleted by a different user:

.. code-block:: python

    from django_notification.models.notification import Notification

    notifications = Notification.objects.sent(
        recipients=user_instance, exclude_deleted_by=user_instance
    )


Return All Unsent Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``unsent`` method retrieves all unsent notifications, excluding those that have been soft-deleted by the specified user. It allows filtering based on recipients, groups, and additional conditions.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.unsent(
      recipients,
      exclude_deleted_by,
      groups,
      display_detail,
      conditions,
  ) -> QuerySet

**Arguments:**

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
  Optional filter for notifications based on recipients. Can be:

  - A single ``UserModel`` instance.
  - A ``QuerySet`` of ``UserModel`` instances.
  - A list of ``UserModel`` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **exclude_deleted_by** (``Optional[UserModel]``):
  Optional filter to exclude notifications that have been soft-deleted by a specific user. If provided, the method excludes all notifications that have been marked as deleted by this user.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
  Optional filter for notifications based on groups. Can be:

  - A single ``Group`` instance.
  - A ``QuerySet`` of ``Group`` instances.
  - A list of ``Group`` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (``Optional[bool]``):
  Indicates whether to return simplified details.

  - If ``True``, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If ``False``, the method returns a ``QuerySet`` of notification instances.

- **conditions** (``Optional[Q]``):
  Additional filter conditions. Accepts a ``Q`` object from ``django.db.models`` for specifying extra conditions that may be needed for various contexts. Defaults to ``Q()`` (no additional conditions).

**Returns:**

- A `QuerySet` of unsent notifications, or a dictionary of simplified details if `display_detail` is `True`.

**Example Usage:**

To retrieve all unsent notifications for a specific user, excluding those deleted by a different user:

.. code-block:: python

    from django_notification.models.notification import Notification

    unsent_notifications = Notification.objects.unsent(
        recipients=user_instance, exclude_deleted_by=user_instance
    )



Return All Seen Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``seen`` method returns all notifications that have been seen by the given user.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.seen(
      seen_by,
      recipients,
      groups,
      display_detail,
      conditions,
  ) -> QuerySet

**Arguments:**

- **seen_by** (``UserModel``):
  The user who has seen the notifications.

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
  Optional filter for notifications based on recipients (users). Can be:

  - A single ``UserModel`` instance.
  - A ``QuerySet`` of ``UserModel`` instances.
  - A list of ``UserModel`` instances.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
  Optional filter for notifications based on groups. Can be:

  - A single ``Group`` instance.
  - A ``QuerySet`` of ``Group`` instances.
  - A list of ``Group`` instances.

- **display_detail** (``Optional[bool]``):
  Indicates whether to return simplified details using `.values()`. If ``False``, it returns the ``QuerySet`` of notifications.

- **conditions** (``Optional[Q]``):
  Additional filter conditions using a ``Q`` object. Defaults to ``Q()`` (no additional conditions).

**Returns:**

- A `QuerySet` of seen notifications, or a dictionary of simplified details if `display_detail` is `True`.

----

Return All Unseen Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``unseen`` method returns all notifications that the given user has not seen.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.unseen(
      unseen_by,
      recipients,
      groups,
      display_detail,
      conditions,
  ) -> QuerySet


**Arguments:**

- **unseen_by** (``UserModel``):
  The user who has not seen the notifications.

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
  Optional filter for notifications based on recipients (users). Can be:

  - A single ``UserModel`` instance.
  - A ``QuerySet`` of ``UserModel`` instances.
  - A list of ``UserModel`` instances.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
  Optional filter for notifications based on groups. Can be:

  - A single ``Group`` instance.
  - A ``QuerySet`` of ``Group`` instances.
  - A list of ``Group`` instances.

- **display_detail** (``Optional[bool]``):
  Indicates whether to return simplified details using `.values()`. If ``False``, it returns the ``QuerySet`` of notifications.

- **conditions** (``Optional[Q]``):
  Additional filter conditions using a ``Q`` object. Defaults to ``Q()`` (no additional conditions).

**Returns:**

- A `QuerySet` of unseen notifications, or a dictionary of simplified details if `display_detail` is `True`.

----

Mark All as Seen
------------------------------

The ``mark_all_as_seen`` method marks all notifications as seen by the specified user if they are recipients or group members or ADMIN.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.mark_all_as_seen(user) -> int

**Arguments:**

- **user** (``UserModel``):
  The user for whom all notifications will be marked as seen.

**Returns:**

- The number of notifications marked as seen.

----

Mark All as Sent
~~~~~~~~~~~~~~~~

This method marks notifications as sent for the specified recipients or groups.

**Method Signature**

.. code-block:: shell

    from django_notification.models.notification import Notification

    Notification.objects.mark_as_sent(
    recipients,
    groups,
    ) -> int

**Arguments:**

- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``):
   Optional filter for notifications based on recipients.

- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``):
   Optional filter for notifications based on groups.

**Returns:**

- The number of notifications marked as sent.

----

Return Deleted Notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method returns all deleted (soft deleted) notifications, optionally filtered by the user who deleted them.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.deleted(
      deleted_by=None
  ) -> QuerySet

**Arguments:**

- **deleted_by** (``Optional[UserModel]``):
  Optional filter to return notifications deleted by a specific user.

**Returns:**

- A `QuerySet` of deleted notifications.

----

Clear Notifications
~~~~~~~~~~~~~~~~~~~
This method moves notifications for the specified user into a 'deleted' state by creating instances in the `DeletedNotifications` model.

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.clear_all(user) -> None

**Arguments:**

- **user** (``UserModel``):
  The user for whom notifications will be cleared (soft deleted).

**Returns:**

- None.

----

Create a Notification
~~~~~~~~~~~~~~~~~~~~~

The `create_notification` method provides a convenient way to generate and store notifications in your Django application. This method is part of the `Notification` model and is used to create notifications with various attributes. Below is an overview of how to use this method effectively:

**Method Signature**

 .. code-block:: python

    from django_notification.models.notification import Notification

    Notification.objects.create_notification(
        verb,
        actor,
        description,
        recipients,
        groups,
        status,
        public,
        target,
        action_object,
        link,
        is_sent,
        data,
    )


**Arguments:**

- **verb** (``str``): A description of the action (e.g., "Logged in", "Created an item").
- **actor** (``Model``): The model instance that performs the action (e.g., user, system).
- **description** (``Optional[str]``): Optional additional information.
- **recipients** (``Optional[Union[UserModel, QuerySet, List[UserModel]]]``): One or more users who will receive the notification.
- **groups** (``Optional[Union[Group, QuerySet, List[Group]]]``): Optional user groups who will receive the notification.
- **status** (``Optional[str]``): Notification status (default is ``NotificationStatus.INFO``).
- **public** (``bool``): Whether the notification is public (default is ``True``).
- **target** (``Optional[Model]``): Optional target object related to the notification.
- **action_object** (``Optional[Model]``): Optional object that is the focus of the action.
- **link** (``Optional[str]``): Optional URL link related to the notification.
- **is_sent** (``bool``): Marks whether the notification is sent (default is ``False``).
- **data** (``Optional[Dict]``): Optional additional data in dictionary format(JSON Field).

**Returns:**

- created notification instance.

**Example Usage**

Here's an example of how to use the ``create_notification`` method to generate a notification:

.. code-block:: python

    from django.contrib.auth.models import User
    from django_notification.models.notification import Notification
    from django_notification.models.helper.enums.status_choices import NotificationStatus


    # Example data
    actor = User.objects.get(username="john_doe")
    recipients = [User.objects.get(username="jane_doe")]
    description = "John Doe logged in to the admin panel."

    # Creating a notification
    notification = Notification.objects.create_notification(
        verb="Logged in to admin panel",
        actor=actor,
        description=description,
        recipients=recipients,
        status=NotificationStatus.INFO,
        public=True,
        link="http://example.com/admin",
        is_sent=True,
    )

**Note**: The ``description`` field is used as the title of the notification, which includes a time since the action occurred (e.g., "User logged in to admin area a minute ago."). If not provided, a default title will be generated based on the actor, verb, and other fields.

----

Update a Notification
~~~~~~~~~~~~~~~~~~~~~

This method updates some editable fields of a notification by its ID.

**Method Signature**

.. code-block:: python

  from django_notification.models.notification import Notification

  Notification.objects.update_notification(
      notification_id, is_sent=None, public=None, data=None
  )

**Arguments:**

- **notification_id** (``int``):
  The ID of the notification to update.

- **is_sent** (``bool``):
  The updated sent status of the notification. Defaults to ``True``.

- **public** (``bool``):
  The updated public status of the notification. Defaults to ``True``.

- **data** (``Optional[JSONField]``):
  Optional additional data to store with the notification.

**Returns:**

- None.

----

Delete a Notification
~~~~~~~~~~~~~~~~~~~~~

This method deletes a notification by its ID. If `soft_delete` is `True`, it moves the notification to the `DeletedNotifications` model; otherwise, it removes the notification instance (requires admin role).

**Method Signature**

.. code-block:: shell

  from django_notification.models.notification import Notification

  Notification.objects.delete_notification(
      notification_id,
      recipient=None,
      soft_delete=True
  ) -> None

**Arguments:**

- **notification_id** (``int``):
  The ID of the notification to delete.

- **recipient** (``Optional[UserModel]``):
  Optional user instance to filter the notification by recipient.

- **soft_delete** (``bool``):
  If `True`, the notification is soft-deleted (moved to `DeletedNotifications`). If `False`, the notification is permanently deleted (requires admin role).

**Returns:**

- None.
