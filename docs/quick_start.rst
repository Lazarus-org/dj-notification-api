Create your first inbox
========================

Add notification routes to an existing Django project, create a message and
move it from unread to read. Email and WebSockets can be added afterward.

Install and configure
----------------------

Install into your project's virtual environment::

    python -m pip install dj-notification-api

Supported combinations are Python 3.10/3.11 with Django 5.2, or Python
3.12–3.14 with Django 5.2, 6.0 or 6.1. DRF 3.18 and ``django-filter`` are
runtime dependencies. Check your installed release's requirements when
upgrading an existing environment.

Add the apps alongside your existing Django apps::

    # config/settings.py
    INSTALLED_APPS = [
        # Existing auth, contenttypes, sessions and project apps ...
        "rest_framework",
        "django_notification",
    ]

Include the router in your root URL configuration::

    # config/urls.py
    from django.urls import include, path

    urlpatterns = [
        path("notification/", include("django_notification.api.routers.notification")),
    ]

Create the tables and check configuration::

    python manage.py migrate
    python manage.py check

Migrations create the default ``general`` category. No event receiver or
background process is needed. Installing ``django-filter`` does not enable
an extra filterset automatically; the built-in category/priority filters
work without one.

Create a message
-----------------

Open ``python manage.py shell``. Replace the usernames below with existing
accounts. The example also works with a different ``USERNAME_FIELD``::

    from django.contrib.auth import get_user_model
    from django_notification.models import Notification

    User = get_user_model()
    actor = User.objects.get(**{User.USERNAME_FIELD: "alex"})
    recipient = User.objects.get(**{User.USERNAME_FIELD: "sam"})

    notification = Notification.objects.create_notification(
        actor=actor,
        verb="assigned you a task",
        recipients=[recipient],
        description="Review the delivery schedule before Friday.",
        link="https://app.example.com/tasks/42",
        is_sent=True,
    )

Keep creation in trusted application code, such as a task-assignment service.
There is no public REST creation endpoint. The default ``is_sent=False``
creates a draft; omit ``is_sent=True`` only when you intend to send it later.

Follow the read-state flow
---------------------------

The API uses your project's DRF authentication. This shell example uses DRF's
test client so it does not assume a particular token package::

    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=recipient)  # Shell/test use only.
    base = "/notification/notifications/"
    item_id = notification.pk

    inbox = client.get(base).json()
    assert item_id in [item["id"] for item in inbox["results"]]

    preview = client.get(f"{base}{item_id}/preview/")
    assert preview.status_code == 200
    assert preview.json()["description"] == notification.description

    result = client.post(f"{base}{item_id}/mark_seen/").json()
    assert result == {"id": item_id, "seen": True, "changed": True}

    repeated = client.post(f"{base}{item_id}/mark_seen/").json()
    assert repeated["changed"] is False

    activity = client.get("/notification/activities/").json()
    assert item_id in [item["id"] for item in activity["results"]]

This assumes default pagination and fewer than ten matching items. Follow
``next`` for more pages. In a browser use your normal session or token login;
``force_authenticate()`` is for tests, not an application login mechanism.
Session-authenticated writes need the application's CSRF token.

Detail and preview GETs are read-only by default. After marking an item seen,
its unread-detail URL returns ``404``; preview still works, and
``activities/{id}/`` provides read detail.

Clear or mark unread
---------------------

Return the read item to the unread inbox::

    client.post(f"{base}{item_id}/mark_unseen/")

To clear it, mark it seen and delete its activity::

    client.post(f"{base}{item_id}/mark_seen/")
    response = client.delete(f"/notification/activities/{item_id}/")
    assert response.status_code == 204

This clears the item only for Sam. Other recipients keep their own state.
There is no public restore-cleared endpoint. Permanent deletion is a separate
trusted administration operation.

Connect a business transaction
-------------------------------

When a business change and its notification must succeed together, create
them in the same database transaction::

    from django.db import transaction

    with transaction.atomic():
        # Save the task assignment using your application's model here.
        Notification.objects.create_notification(
            actor=actor,
            recipients=[recipient],
            verb="assigned you a task",
            is_sent=True,
            idempotency_key="tasks:42:assignment:7",
        )

Use a stable logical event identity for ``idempotency_key``. Retrying the
same arguments returns the original notification. An assignment event key
must differ from the key for a later reassignment of the same task.
See :doc:`usage` for key scope and deduplication windows.

Next steps
-----------

* :doc:`concepts` explains audiences, preferences and independent state.
* :doc:`api_guide` covers payloads, pagination, errors and client actions.
* :doc:`delivery` walks through console email and production workers.
* :doc:`troubleshooting` diagnoses an empty inbox or missing external send.
