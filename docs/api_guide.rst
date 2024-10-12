API Guide
=========

This section provides a detailed overview of the Django Notification API, allowing users to manage notifications efficiently. The API exposes two main endpoints:

1. **notification/notifications/**:

   - Lists all unseen notifications.
   - Retrieves a single unseen notification.
   - Marks all notifications as seen (action: ``mark_all_as_seen``).

2. **notification/activities/**:

   - Lists all seen notifications.
   - Retrieves a single seen notification.
   - Soft deletes all seen notifications (action: ``clear_activities``).
   - Soft deletes a single seen notification (action: ``clear_notification``).
   - For Admins:

     - Hard deletes all seen notifications (action: ``delete_activities``).
     - Hard deletes a single seen notification (action: ``delete_notification``).


Notifications API
-----------------

The ``notification/notifications/`` endpoint provides the following features:

- **List unseen notifications**:

  Fetches all unseen notifications for the authenticated user. Controlled by the ``DJANGO_NOTIFICATION_API_ALLOW_LIST`` setting.

- **Retrieve a notification**:

  Retrieves a specific unseen notification by its ID and automatically marks it as seen. Controlled by the ``DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`` setting.

- **Mark all as seen**:

  Marks all unseen notifications for the user as seen. Once marked, they move to the ``activities`` endpoint.


Activities API
--------------

The ``notification/activities/`` endpoint offers these features:

- **List seen notifications**:

  Lists all seen notifications for the authenticated user. Controlled by the ``DJANGO_NOTIFICATION_API_ALLOW_LIST`` setting.

- **Retrieve a seen notification**:

  Fetches a specific seen notification by its ID. Controlled by the ``DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`` setting.

- **Clear activities (Soft delete)**:

  Soft deletes all seen notifications, removing them from view without permanent deletion. Controlled by the ``DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE`` setting.

- **Clear a single notification (Soft delete)**:

  Soft deletes a specific seen notification by its ID.

- **Delete activities (Hard delete)**:

  Permanently deletes all seen notifications for ``ADMIN`` users. Controlled by the ``DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE`` setting.

- **Delete a single notification (Hard delete)**:

  Permanently deletes a specific seen notification by its ID (only for ``ADMIN`` users).


Example Responses
-----------------

Here are some examples of responses for each action:


**List notifications with full details**:

.. code-block:: text

   GET /notification/notifications/

   Response:
   HTTP/1.1 200 OK
   Content-Type: application/json

   "results": [
      {
          "id": 1,
          "title": "User logged in to the Admin panel a minute ago",
          "recipient": [
              {
                  "username": "user",
                  "email": "example@domain.com"
              }
          ],
          "group": [],
          "verb": "Logged in to Admin panel",
          "status": "INFO",
          "actor_content_type": 4,
          "target_content_type": null,
          "action_object_content_type": null,
          "link": "<link>",
          "is_sent": true,
          "seen_by": [
              {
                  "username": "admin",
                  "email": "admin@test.com"
              }
          ],
          "public": true,
          "data": null,
          "timestamp": "2024-09-05T13:34:20.969193Z"
      }
   ]

If the ``DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`` setting is ``True``, this detailed response will be returned for all users.

**List notifications with simplified data**:

.. code-block:: text

   GET /notification/notifications/

   Response:
   HTTP/1.1 200 OK
   Content-Type: application/json

   "results": [
      {
          "id": 1,
          "title": "User accepted your request 5 seconds ago",
          "status": "INFO",
          "link": "<link>",
          "timestamp": "2024-09-05T13:34:20.969193Z"
      },

      ...
   ]

This response is returned when ``DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`` is set to ``False``. Admins always see full details.

**Mark all as seen**:

.. code-block:: text

   GET /notification/notifications/mark_all_as_seen/

   Response:
   HTTP/1.1 200 OK

   "detail": "3 Notifications marked as seen."


**Clear activities (soft delete)**:

.. code-block:: text

   GET /notification/activities/clear_activities/

   Response:
   HTTP/1.1 204 No Content

   "detail": "All activities cleared."


**Clear a single notification (soft delete)**:

.. code-block:: text

   GET /notification/activities/1/clear_notification/

   Response:
   HTTP/1.1 204 No Content

   "detail": "Notification 1 cleared."


**Delete all activities (hard delete)**:

.. code-block:: text

   GET /notification/activities/delete_activities/

   Response:
   HTTP/1.1 204 No Content

   "detail": "All activities deleted."


**Delete a single notification (hard delete)**:

.. code-block:: text

   GET /notification/activities/3/delete_notification/

   Response:
   HTTP/1.1 204 No Content

   "detail": "Notification 3 deleted."

**Note**: you can exclude Any fields with a ``null`` value in the response output by adding this config in your ``settings.py``:
.. code-block:: python

   DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS = True

Throttling
----------

The API includes a built-in throttling mechanism that limits the number of requests a user can make based on their role. You can customize these throttle limits in the settings file.

To specify the throttle rates for authenticated users and staff members, add the following in your settings:

.. code-block:: ini

   DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "100/day"
   DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "60/minute"

These settings limit the number of requests users can make within a given timeframe.

**Note:** You can define custom throttle classes and reference them in your settings.


Filtering, Ordering, and Search
-------------------------------

The API supports filtering, ordering, and searching of notifications. Filter Class can be applied optionally, allowing users to narrow down results.

Options include:

- **Filtering**: By default filtering feature is not included, If you want to use this, you need to add ``django_filters`` to your `INSTALLED_APPS` and provide the path to the ``NotificationFilter`` class (``"django_notification.api.filters.notification_filter.NotificationFilter"``). Alternatively, you can use a custom filter class if needed.

  - **Note**: for more clarification, refer to the `DJANGO_NOTIFICATION_API_FILTERSET_CLASS` in :doc:`Settings <settings>` section.

- **Ordering**: Results can be ordered by fields such as ``id``, ``timestamp``, or ``public``.

- **Search**: You can search fields like ``verb`` and ``description``.

These fields can be customized by adjusting the related configurations in your Django settings.


Pagination
----------

The API supports limit-offset pagination, with configurable minimum, maximum, and default page size limits. This controls the number of results returned per page.

Permissions
-----------

The base permission for all endpoints is ``IsAuthenticated``, meaning users must be logged in to access the API. You can extend this by creating custom permission classes to implement more specific access control.

For instance, you can allow only specific user roles to perform certain actions.

Parser Classes
--------------

The API supports multiple parser classes that control how data is processed. The default parsers include:

- ``JSONParser``
- ``MultiPartParser``
- ``FormParser``

You can modify parser classes by updating the API settings to include additional parsers or customize the existing ones to suit your project.

----

Each feature can be configured through the Django settings file. For further details, refer to the :doc:`Settings <settings>` section.
