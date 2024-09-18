Quick Start
===========

This section provides a fast and easy guide to getting the `dj-notification-api` package up and running in your Django project. Follow the steps below to quickly set up the package and start creating notifications.

1. Install the Package
----------------------

**Option 1: Using `pip` (Recommended)**

Install the package via pip:

.. code-block:: bash

   pip install dj-notification-api

**Option 2: Using `Poetry`**

If you're using Poetry, add the package with:

.. code-block:: bash

   poetry add dj-notification-api

**Option 3: Using `pipenv`**

If you're using pipenv, install the package with:

.. code-block:: bash

   pipenv install dj-notification-api


2. Add to Installed Apps
------------------------

Once installed, add `django_notification` to the `INSTALLED_APPS` in your Django `settings.py` file:

.. code-block:: shell

   INSTALLED_APPS = [
       ...
       "django_notification",
       ...
   ]


3. Apply Migrations
-------------------

Run the following command to apply the necessary migrations:

.. code-block:: bash

   python manage.py migrate


4. Add Notification API URLs
----------------------------

Include the notification API routes in your project’s `urls.py` file:

.. code-block:: python

   from django.urls import path, include

   urlpatterns = [
       # ...
       path("notification/", include("django_notification.api.routers.notification")),
       # ...
   ]


5. Create Notifications
-----------------------

To create notifications and use them in your project, use the `Notification` model from the `django_notification` package. The `create_notification` method allows you to generate notifications dynamically based on various events in your application.

**Example:**

.. code-block:: python

   from django.contrib.auth.models import User
   from django_notification.models.notification import Notification
   from django_notification.models.helper.enums.status_choices import NotificationStatus

   # Define the actor and recipients
   actor = User.objects.get(username="admin")
   recipient = User.objects.get(username="john_doe")

   # Create a new notification
   Notification.queryset.create_notification(
       verb="Logged in to Admin panel",
       actor=actor,
       recipients=[recipient],
       description="User logged in to admin area.",
       status=NotificationStatus.INFO,
       public=True,
       link="https://example.com/admin/dashboard",
       is_sent=True,
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
- **data** (``Optional[Dict]``): Optional additional data in dictionary format.

**Note**: The ``description`` field is used as the title of the notification, and it will be displayed with a time-relative format, such as: ``User logged in to admin area a minute ago.``

If the ``description`` is not provided, a title will be automatically generated based on several fields like the ``actor``, ``verb``, and other relevant fields (e.g., target or action object).


6. Verify Notifications
-----------------------

Once notifications are created, they can be managed through the API endpoints. To test and verify the creation, make a request to the relevant endpoint, for example:

.. code-block:: bash

   curl -X GET http://localhost:8000/notification/notifications/

This will return a list of notifications created for the authenticated user.


7. Start Using the API
----------------------

With the setup complete, the notification API is ready for use in your project. For further customizations and settings, refer to the **API Guide** and **Settings** sections.
