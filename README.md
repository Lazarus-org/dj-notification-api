# Welcome to dj-notification-api Documentation!

[![License](https://img.shields.io/github/license/lazarus-org/dj-notification-api)](https://github.com/lazarus-org/dj-notification-api/blob/main/LICENSE)
[![PyPI Release](https://img.shields.io/pypi/v/dj-notification-api)](https://pypi.org/project/dj-notification-api/)
[![Documentation](https://img.shields.io/readthedocs/dj-notification-api)](https://dj-notification-api.readthedocs.io/en/latest/)
[![Pylint Score](https://img.shields.io/badge/pylint-10/10-brightgreen?logo=python&logoColor=blue)](https://www.pylint.org/)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/dj-notification-api)](https://pypi.org/project/dj-notification-api/)
[![Supported Django Versions](https://img.shields.io/pypi/djversions/dj-notification-api)](https://pypi.org/project/dj-notification-api/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=yellow)](https://github.com/pre-commit/pre-commit)
[![Open Issues](https://img.shields.io/github/issues/lazarus-org/dj-notification-api)](https://github.com/lazarus-org/dj-notification-api/issues)
[![Last Commit](https://img.shields.io/github/last-commit/lazarus-org/dj-notification-api)](https://github.com/lazarus-org/dj-notification-api/commits/main)
[![Languages](https://img.shields.io/github/languages/top/lazarus-org/dj-notification-api)](https://github.com/lazarus-org/dj-notification-api)
[![Coverage](https://codecov.io/gh/lazarus-org/dj-notification-api/branch/main/graph/badge.svg)](https://codecov.io/gh/lazarus-org/dj-notification-api)

[`dj-notification-api`](https://github.com/lazarus-org/dj-notification-api/) is a Django package developed by Lazarus designed to simplify and optimize the process of managing notifications through various APIs.
With this package, you can easily integrate a notification system into your Django project by just installing it. it offers a fully customizable notification API that can be tailored to suit your specific needs.

It also provides an intuitive and powerful admin interface, allowing you to manage, track, and configure notifications effortlessly. Enjoy the flexibility and performance optimizations built into the package.

## Project Detail

- Language: Python >= 3.9
- Framework: Django >= 4.2
- Django REST Framework >= 3.14

## Documentation Overview

The documentation is organized into the following sections:

- **[Quick Start](#quick-start)**: Get up and running quickly with basic setup instructions.
- **[API Guide](#api-guide)**: Detailed information on available APIs and endpoints.
- **[Usage](#usage)**: How to effectively use the package in your projects.
- **[Settings](#settings)**: Configuration options and settings you can customize.


---

# Quick Start

This section provides a fast and easy guide to getting the `dj-notification-api` package up and running in your Django project. Follow the steps below to quickly set up the package and start creating notifications.

## 1. Install the Package

**Option 1: Using `pip` (Recommended)**

Install the package via pip:

```bash
$ pip install dj-notification-api
```

**Option 2: Using `poetry`**

If you're using Poetry, add the package with:

```bash
$ poetry add dj-notification-api
```

**Option 3: Using `pipenv`**

```bash
$ pipenv install dj-notification-api
```

## 2. Add to Installed Apps

Once installed,  ensure that both `rest_framework` and `django_notification` are added to the `INSTALLED_APPS` in your Django `settings.py` file::

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",  # Required for API support

    "django_notification",
    # ...
]
```

## 3. (Optional) Configure API Filters

To enable filtering of notifications through the API, include `django_filters` in your `INSTALLED_APPS` and configure the filter settings.

Add `django_filters` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_filters",
    # ...
]
```

Then, set the filter class configuration in your `settings.py`:
```python
DJANGO_NOTIFICATION_API_FILTERSET_CLASS = "django_notification.api.filters.notification_filter.NotificationFilter"
```

## 4. Apply Migrations

Run the following command to apply the necessary migrations:
```shell
python manage.py migrate
```

## 5. Add Notification API URLs

Include the notification API routes in your project’s `urls.py` file:
```python
from django.urls import path, include

urlpatterns = [
    # ...
    path("notification/", include("django_notification.api.routers.notification")),
    # ...
]
```

## 6. Create Notifications

To create notifications and use them in your project, use the `Notification` model from the `django_notification` package. The `create_notification` method allows you to generate notifications dynamically based on various events in your application.

### Example:

```python
from django.contrib.auth.models import User
from django_notification.models.notification import Notification
from django_notification.models.helper.enums.status_choices import NotificationStatus

# Define the actor and recipients
actor = User.objects.get(username="admin")
recipient = User.objects.get(username="john_doe")

# Create a new notification
Notification.objects.create_notification(
    verb="Logged in to Admin panel",
    actor=actor,
    recipients=[recipient],
    description="User logged in to admin area.",
    status=NotificationStatus.INFO,
    public=True,
    link="https://example.com/admin/dashboard",
    is_sent=True,
)
```

**Arguments:**

- **verb** (`str`): A description of the action (e.g., "Logged in", "Created an item").
- **actor** (`Model`): The model instance that performs the action (e.g., user, system).
- **description** (`Optional[str]`): Optional additional information.
- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`): One or more users who will receive the notification.
- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`): Optional user groups who will receive the notification.
- **status** (`Optional[str]`): Notification status (default is `NotificationStatus.INFO`).
- **public** (`bool`): Whether the notification is public (default is `True`).
- **target** (`Optional[Model]`): Optional target object related to the notification.
- **action_object** (`Optional[Model]`): Optional object that is the focus of the action.
- **link** (`Optional[str]`): Optional URL link related to the notification.
- **is_sent** (`bool`): Marks whether the notification is sent (default is `False`).
- **data** (`Optional[Dict]`): Optional additional data in dictionary format (JSON Field).

**Note**: The `description` field is used as the title of the notification, and it will be displayed with a time-relative format, such as: `User logged in to admin area a minute ago.`

If the `description` is not provided, a title will be automatically generated based on several fields like the `actor`, `verb`, and other relevant fields (e.g., target or action object).


### 7. Verify Notifications

Once notifications are created, they can be managed through the API endpoints. To test and verify the creation, make a request to the relevant endpoint, for example:

```bash
curl -X GET http://localhost:8000/notification/notifications/
```
This will return a list of notifications created for the authenticated user.


With the setup complete, the `django_notification` is ready for use in your project. For further customizations and settings, refer to the [API Guide](api_guide) and [Settings](settings) sections.

---

# API Guide

This section provides a detailed overview of the Django Notification API, allowing users to manage notifications efficiently. The API exposes two main endpoints:

1. **notification/notifications/**:

   - Lists all unseen notifications.
   - Retrieves a single unseen notification.
   - Marks all notifications as seen (action: `mark_all_as_seen`).

2. **notification/activities/**:

   - Lists all seen notifications.
   - Retrieves a single seen notification.
   - Soft deletes all seen notifications (action: `clear_activities`).
   - Soft deletes a single seen notification (action: `clear_notification`).
   - For Admins:
     - Hard deletes all seen notifications (action: `delete_activities`).
     - Hard deletes a single seen notification (action: `delete_notification`).

## Notifications API

The `notification/notifications/` endpoint provides the following features:

- **List unseen notifications**:
  Fetches all unseen notifications for the authenticated user. Controlled by the `DJANGO_NOTIFICATION_API_ALLOW_LIST` setting.

- **Retrieve a notification**:
  Retrieves a specific unseen notification by its ID and automatically marks it as seen. Controlled by the `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE` setting.

- **Mark all as seen**:
  Marks all unseen notifications for the user as seen. Once marked, they move to the `activities` endpoint.

## Activities API

The `notification/activities/` endpoint offers these features:

- **List seen notifications**:
  Lists all seen notifications for the authenticated user. Controlled by the `DJANGO_NOTIFICATION_API_ALLOW_LIST` setting.

- **Retrieve a seen notification**:
  Fetches a specific seen notification by its ID. Controlled by the `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE` setting.

- **Clear activities (Soft delete)**:
  Soft deletes all seen notifications, removing them from view without permanent deletion. Controlled by the `DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE` setting.

- **Clear a single notification (Soft delete)**:
  Soft deletes a specific seen notification by its ID.

- **Delete activities (Hard delete)**:
  Permanently deletes all seen notifications for `ADMIN` users. Controlled by the `DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE` setting.

- **Delete a single notification (Hard delete)**:
  Permanently deletes a specific seen notification by its ID (only for `ADMIN` users).

## Example Responses

Here are some examples of responses for each action:

### List notifications with full details:

```http
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
```

### List notifications with simplified data:

```http
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
```
This response is returned when `DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS` is set to `False`. Admins always see full details.

### Mark all as seen:

```http
GET /notification/notifications/mark_all_as_seen/

Response:
HTTP/1.1 200 OK

"detail": "3 Notifications marked as seen."
```

### Clear activities (soft delete):

```http
GET /notification/activities/clear_activities/

Response:
HTTP/1.1 204 No Content

"detail": "All activities cleared."

```

### Clear a single notification (soft delete):

```http
GET /notification/activities/1/clear_notification/

Response:
HTTP/1.1 204 No Content

"detail": "Notification 1 cleared."

```

### Delete all activities (hard delete):

```http
GET /notification/activities/delete_activities/

Response:
HTTP/1.1 204 No Content

"detail": "All activities deleted."
```

### Delete a single notification (hard delete):

```http
GET /notification/activities/3/delete_notification/

Response:
HTTP/1.1 204 No Content

"detail": "Notification 3 deleted."

```
**Note**: you can exclude Any fields with a `null` value in the response output by adding this config in your `settings.py`:
```python
DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS = True
```

## Throttling

The API includes a built-in throttling mechanism that limits the number of requests a user can make based on their role. You can customize these throttle limits in the settings file.

To specify the throttle rates for authenticated users and staff members, add the following in your settings:

```python
DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "100/day"
DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "60/minute"
```
These settings limit the number of requests users can make within a given timeframe.

**Note:** You can define custom throttle classes and reference them in your settings.

## Filtering, Ordering, and Search

The API supports filtering, ordering, and searching of notifications. A filter class can be applied optionally, allowing users to narrow down results.

### Options include:

- **Filtering**: By default, the filtering feature is not included. If you want to use this, you need to add `django_filters` to your `INSTALLED_APPS` and provide the path to the `NotificationFilter` class (`"django_notification.api.filters.notification_filter.NotificationFilter"`). Alternatively, you can use a custom filter class if needed.

  - **Note**: For more clarification, refer to the `DJANGO_NOTIFICATION_API_FILTERSET_CLASS` in the [Settings](#settings) section.

- **Ordering**: Results can be ordered by fields such as `id`, `timestamp`, or `public`.

- **Search**: You can search fields like `verb` and `description`.

These fields can be customized by adjusting the related configurations in your Django settings.

## Pagination

The API supports limit-offset pagination, with configurable minimum, maximum, and default page size limits. This controls the number of results returned per page.

## Permissions

The base permission for all endpoints is `IsAuthenticated`, meaning users must be logged in to access the API. You can extend this by creating custom permission classes to implement more specific access control.

For instance, you can allow only specific user roles to perform certain actions.

## Parser Classes

The API supports multiple parser classes that control how data is processed. The default parsers include:

- `JSONParser`
- `MultiPartParser`
- `FormParser`

You can modify parser classes by updating the API settings to include additional parsers or customize the existing ones to suit your project.


Each feature can be configured through the Django settings file. For further details, refer to the [Settings](#settings) section.

---

# Usage

This section provides a comprehensive guide on how to utilize the package's key features, including the functionality of the Django admin panels for managing notifications and deleted notifications, and queryset methods for handling notifications.

## Admin Site

If you are using a **custom admin site** in your project, you must pass your custom admin site configuration in your Django settings. Otherwise, Django may raise the following error during checks:

```shell
ERRORS:
<class 'django_notification.admin.deleted_notification.DeletedNotificationAdmin'>:
 (admin.E039) An admin for model "User" has to be registered to be referenced by DeletedNotificationAdmin.autocomplete_fields.
```
To resolve this, In your `settings.py`, add the following setting to specify the path to your custom admin site class instance:
```python
DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = "path.to.your.custom.site"
```
example of a custom Admin Site:
```python
from django.contrib.admin import AdminSite

class CustomAdminSite(AdminSite):
    site_header = "Custom Admin"
    site_title = "Custom Admin Portal"
    index_title = "Welcome to the Custom Admin Portal"

# Instantiate the custom admin site as example
example_admin_site = CustomAdminSite(name='custom_admin')
```
and then reference the instance like this:

```python
DJANGO_NOTIFICATION_ADMIN_SITE_CLASS = "path.to.example_admin_site"
```
This setup allows `dj-notification-api` to use your custom admin site for it's Admin interface, preventing any errors and ensuring a smooth integration with the custom admin interface.

## Notifications Admin Panel

The `NotificationAdmin` class provides a comprehensive admin interface for managing notifications in the Django admin panel. The features and functionality are described below:

### Admin Actions

- **Mark as Sent**:

  An admin action that allows you to mark selected notifications as sent. When this action is performed, the `is_sent` field of the selected notifications will be updated to `True`. After execution, the admin will receive feedback indicating how many notifications were successfully updated.

### Inline Admin Interfaces

The `NotificationAdmin` panel includes two inline admin interfaces that allow admins to view and manage related models directly from the notification page:

- **NotificationRecipientInline**:

  Displays and manages the recipients associated with each notification. Admins can view or add recipient information directly within the notification details page.

- **NotificationSeenInline**:

  Displays and manages the records of when notifications were seen by recipients. This provides visibility into which recipients have already viewed the notification.

### List Display

The list view for notifications includes the following fields:

- `ID`: The unique identifier for each notification.
- `Title`: The notification title or a summary.
- Sent Status (`is_sent`): Indicates whether the notification has been sent.
- `Public` Status: Indicates if the notification is public.
- `Timestamp`: The time when the notification was created.

This view helps admins get a quick overview of the notifications and their current status.

### Filtering

Admins can filter the list of notifications based on the following fields:

- `is_sent`: Filter by whether the notification has been sent or not.
- `public`: Filter by whether the notification is public or private.
- `timestamp`: Filter by the creation time of the notification.

These filters make it easier to find specific notifications or groups of notifications based on status or time.

### Search Functionality

Admins can search for notifications using the following fields:

- `ID`: The unique identifier of the notification.
- `Recipient Username`: The username of the recipient associated with the notification.
- `Group Name`: The name of the group associated with the notification.

This search functionality enables quick access to specific notifications by key identifiers.

### Pagination

The admin list view displays **10 notifications per page** by default. This can help improve load times and make it easier for admins to manage large lists of notifications.

### Permissions Configuration

The admin permissions for `add`, `change`, and `delete` actions can be controlled through the following Django settings:

- `DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION`: Controls whether the "add" action is available in the Notifications and Deleted Notifications Admin. Defaults to `False`.

- `DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION`: Controls whether the "change" action is allowed in the Notifications and Deleted Notifications Admin. Defaults to `False`.

- `DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION`: Controls whether the "delete" action is available in the Notifications and Deleted Notifications Admin. Defaults to `False`.



## Deleted Notifications Admin Panel

The Deleted Notifications Admin interface allows admins to manage notifications that have been marked as deleted. Admins can view, filter, and search through deleted notifications to ensure better tracking and management.

### Key Features

- **Autocomplete Fields**:

  - Autocomplete is available for the `notification` and `user` fields to facilitate quick selection.

- **List Display**:

  The admin interface shows the following fields in the list view:

  - `Notification ID`: The ID of the deleted notification.
  - `Title`: The title of the deleted notification.
  - `Deleted by`: The username of the user who deleted the notification.
  - `Deleted at`: The timestamp indicating when the notification was deleted.

- **List Filters**:

  - The admin interface allows filtering by the `deleted_at` timestamp, making it easy to view notifications deleted within specific time periods.

- **Pagination**:

  - By default, the list view displays **10 deleted notifications per page**, improving the performance of the admin interface when dealing with large numbers of entries.

### Search Functionality

Admins can search for deleted notifications using the following fields:

- `Notification ID`: Search by the unique identifier of the deleted notification.
- `Username`: Search by the username of the user who deleted the notification.

### Search Logic

Users can perform searching based on the following functionality:

- **Notification ID Search**: If the search term is a number, searches by the notification ID.
- **Username Search**: If the search term is a string, filters based on the username of the user who deleted the notification.

---

## NotificationDataAccessLayer (Manager)

The `django_notification` package provides a Manager class with various methods to interact with notifications in different contexts. Users typically use `Notification.objects.create_notification()` to create notifications, but other methods are available for querying and managing notifications. Below is an overview of the available methods:

### Return All Notifications

This method retrieves all notifications. It allows filtering based on recipients and groups.

**Method Signature**

```shell
from django_notification.models.notification import Notification

Notification.objects.all_notifications(
    recipients,
    groups,
    display_detail,
) -> QuerySet
```
**Arguments:**

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`):
  Optional filter for notifications based on recipients. Can be:
  - A single `UserModel` instance.
  - A `QuerySet` of `UserModel` instances.
  - A list of `UserModel` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`):
  Optional filter for notifications based on groups. Can be:
  - A single `Group` instance.
  - A `QuerySet` of `Group` instances.
  - A list of `Group` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (`Optional[bool]`):
  Indicates whether to return simplified details.
  - If `True`, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If `False`, the method returns a `QuerySet` of notification instances.

**Returns:**

- A `QuerySet` of all notifications, or a dictionary of simplified details if `display_detail` is `True`.

**Example Usage:**

To retrieve all notifications for a specific user:

```python
from django_notification.models.notification import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
user_instance = User.objects.first()

all_notifications = Notification.objects.all_notifications(recipients=user_instance)
```

### Return All sent Notifications

This method retrieves all sent notifications, excluding those that have been soft-deleted by the specified user. It allows filtering based on recipients, groups, and additional conditions.

**Method Signature**

```shell
from django_notification.models.notification import Notification

Notification.objects.sent(
    recipients,
    exclude_deleted_by,
    groups,
    display_detail,
    conditions,
) -> QuerySet
```
**Arguments:**

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`):
  Optional filter for notifications based on recipients. Can be:
  - A single `UserModel` instance.
  - A `QuerySet` of `UserModel` instances.
  - A list of `UserModel` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **exclude_deleted_by** (`Optional[UserModel]`):
  Optional filter to exclude notifications that have been soft-deleted by a specific user. If provided, the method excludes all notifications that have been marked as deleted by this user.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`):
  Optional filter for notifications based on groups. Can be:
  - A single `Group` instance.
  - A `QuerySet` of `Group` instances.
  - A list of `Group` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (`Optional[bool]`):
  Indicates whether to return simplified details.
  - If `True`, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If `False`, the method returns a `QuerySet` of notification instances.

- **conditions** (`Optional[Q]`):
  Additional filter conditions. Accepts a `Q` object from `django.db.models` for specifying extra conditions that may be needed for various contexts. Defaults to `Q()` (no additional conditions).

**Returns:**

- A `QuerySet` of sent notifications, or a dictionary of simplified details if `display_detail` is `True`.

**Example Usage:**

To retrieve all sent notifications for a specific user, excluding those deleted by a user:

```python
from django_notification.models.notification import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
user_instance = User.objects.first()

sent_notifications = Notification.objects.sent(recipients=user_instance, exclude_deleted_by=user_instance)
```

### Return All Unsent Notifications

This method retrieves all unsent notifications, excluding those that have been soft-deleted by the specified user. It allows filtering based on recipients, groups, and additional conditions.

**Method Signature**

```shell
from django_notification.models.notification import Notification

Notification.objects.unsent(
    recipients,
    exclude_deleted_by,
    groups,
    display_detail,
    conditions,
) -> QuerySet
```
**Arguments:**

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`):
  Optional filter for notifications based on recipients. Can be:
  - A single `UserModel` instance.
  - A `QuerySet` of `UserModel` instances.
  - A list of `UserModel` instances.

  If provided, the method returns notifications where the recipients are among the specified recipients.

- **exclude_deleted_by** (`Optional[UserModel]`):
  Optional filter to exclude notifications that have been soft-deleted by a specific user. If provided, the method excludes all notifications that have been marked as deleted by this user.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`):
  Optional filter for notifications based on groups. Can be:
  - A single `Group` instance.
  - A `QuerySet` of `Group` instances.
  - A list of `Group` instances.

  If provided, the method returns notifications where the groups are among the specified groups.

- **display_detail** (`Optional[bool]`):
  Indicates whether to return simplified details.
  - If `True`, the method returns a dictionary of simplified details for each notification using `.values()`.
  - If `False`, the method returns a `QuerySet` of notification instances.

- **conditions** (`Optional[Q]`):
  Additional filter conditions. Accepts a `Q` object from `django.db.models` for specifying extra conditions that may be needed for various contexts. Defaults to `Q()` (no additional conditions).

**Returns:**

- A `QuerySet` of unsent notifications, or a dictionary of simplified details if `display_detail` is `True`.

**Example Usage:**

To retrieve all unsent notifications for a specific user, excluding those deleted by a user:

```python
from django_notification.models.notification import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
user_instance = User.objects.first()

unsent_notifications = Notification.objects.unsent(recipients=user_instance, exclude_deleted_by=user_instance)
```

### Return All Seen Notifications

This method returns all notifications that have been seen by the given user.

**Method Signature**

```shell
Notification.objects.seen(
    seen_by,
    recipients,
    groups,
    display_detail,
    conditions,
) -> QuerySet
```

### Return All Seen Notifications

This method returns all notifications that have been seen by the given user.

**Method Signature**

```shell
Notification.objects.seen(
    seen_by,
    recipients,
    groups,
    display_detail,
    conditions,
) -> QuerySet
```

**Arguments:**

- **seen_by** (`UserModel`):
  The user who has seen the notifications.

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`):
  Optional filter for notifications based on recipients (users). Can be:
  - A single `UserModel` instance.
  - A `QuerySet` of `UserModel` instances.
  - A list of `UserModel` instances.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`):
  Optional filter for notifications based on groups. Can be:
  - A single `Group` instance.
  - A `QuerySet` of `Group` instances.
  - A list of `Group` instances.

- **display_detail** (`Optional[bool]`):
  Indicates whether to return simplified details using `.values()`. If `False`, it returns the `QuerySet` of notifications.

- **conditions** (`Optional[Q]`):
  Additional filter conditions using a `Q` object. Defaults to `Q()` (no additional conditions).

**Returns:**

- A `QuerySet` of seen notifications, or a dictionary of simplified details if `display_detail` is `True`.


### Return All Unseen Notifications

This method returns all notifications that the given user has not seen.

**Method Signature**

```shell
Notification.objects.unseen(
    unseen_by,
    recipients,
    groups,
    display_detail,
    conditions,
) -> QuerySet
```

**Arguments:**

- **unseen_by** (`UserModel`):
  The user who has not seen the notifications.

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`):
  Optional filter for notifications based on recipients (users). Can be:
  - A single `UserModel` instance.
  - A `QuerySet` of `UserModel` instances.
  - A list of `UserModel` instances.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`):
  Optional filter for notifications based on groups. Can be:
  - A single `Group` instance.
  - A `QuerySet` of `Group` instances.
  - A list of `Group` instances.

- **display_detail** (`Optional[bool]`):
  Indicates whether to return simplified details using `.values()`. If `False`, it returns the `QuerySet` of notifications.

- **conditions** (`Optional[Q]`):
  Additional filter conditions using a `Q` object. Defaults to `Q()` (no additional conditions).

**Returns:**

- A `QuerySet` of unseen notifications, or a dictionary of simplified details if `display_detail` is `True`.


This method marks all notifications as seen by the specified user if they are recipients, group members, or ADMIN.

**Method Signature**

```shell
Notification.objects.mark_all_as_seen(user) -> int
```

**Arguments:**

- **user** (`UserModel`):
  The user for whom all notifications will be marked as seen.

**Returns:**

- The number of notifications marked as seen.


### Mark All as Sent

This method marks notifications as sent for the specified recipients or groups.

**Method Signature**

```shell
Notification.objects.mark_as_sent(
    recipients,
    groups,
) -> int
```

**Arguments:**

- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]`):
  Optional filter for notifications based on recipients.

- **groups** (`Optional[Union[Group, QuerySet, List[Group]]`):
  Optional filter for notifications based on groups.

**Returns:**

- The number of notifications marked as sent.


### Return Deleted Notifications

This method returns all deleted (soft deleted) notifications, optionally filtered by the user who deleted them.

**Method Signature**

```shell
Notification.objects.deleted(
    deleted_by=None
) -> QuerySet
```

**Arguments:**

- **deleted_by** (`Optional[UserModel]`):
  Optional filter to return notifications deleted by a specific user.

**Returns:**

- A `QuerySet` of deleted notifications.


### Clear Notifications

This method moves notifications for the specified user into a 'deleted' state by creating instances in the `DeletedNotifications` model.

**Method Signature**

```shell
Notification.objects.clear_all(user) -> None
```

**Arguments:**

- **user** (`UserModel`):
  The user for whom notifications will be cleared (soft deleted).

**Returns:**

- None.


### Create a Notification

The `create_notification` method provides a convenient way to generate and store notifications in your Django application. This method is part of the `Notification` model and is used to create notifications with various attributes. Below is an overview of how to use this method effectively:

**Method Signature**

```shell
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
    data
)
```

**Arguments:**

- **verb** (`str`): A description of the action (e.g., "Logged in", "Created an item").
- **actor** (`Model`): The model instance that performs the action (e.g., user, system).
- **description** (`Optional[str]`): Optional additional information.
- **recipients** (`Optional[Union[UserModel, QuerySet, List[UserModel]]]`): One or more users who will receive the notification.
- **groups** (`Optional[Union[Group, QuerySet, List[Group]]]`): Optional user groups who will receive the notification.
- **status** (`Optional[str]`): Notification status (default is `NotificationStatus.INFO`).
- **public** (`bool`): Whether the notification is public (default is `True`).
- **target** (`Optional[Model]`): Optional target object related to the notification.
- **action_object** (`Optional[Model]`): Optional object that is the focus of the action.
- **link** (`Optional[str]`): Optional URL link related to the notification.
- **is_sent** (`bool`): Marks whether the notification is sent (default is `False`).
- **data** (`Optional[Dict]`): Optional additional data in dictionary format (JSON Field).

**Returns:**

- Created notification instance.

**Example Usage**

Here's an example of how to use the `create_notification` method to generate a notification:

```python
from django.contrib.auth.models import User
from django_notification.models.notification import Notification
from django_notification.models.helper.enums.status_choices import NotificationStatus

# Example data
actor = User.objects.get(username='john_doe')
recipients = [User.objects.get(username='jane_doe')]
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
    is_sent=True
)
```

**Note**: The `description` field is used as the title of the notification, which includes a time since the action occurred (e.g., "User logged in to admin area a minute ago."). If not provided, a default title will be generated based on the actor, verb, and other fields.


### Update a Notification

This method updates some editable fields of a notification by its ID.

**Method Signature**

```shell
Notification.objects.update_notification(
    notification_id,
    is_sent=None,
    public=None,
    data=None
)
```

**Arguments:**

- **notification_id** (`int`):
  The ID of the notification to update.

- **is_sent** (`bool`):
  The updated sent status of the notification.

- **public** (`bool`):
  The updated public status of the notification.

- **data** (`Optional[JSONField]`):
  Optional additional data to store with the notification.

**Returns:**

- None.


### Delete a Notification

This method deletes a notification by its ID. If `soft_delete` is `True`, it moves the notification to the `DeletedNotifications` model; otherwise, it removes the notification instance (requires admin role).

**Method Signature**

```shell
Notification.objects.delete_notification(
    notification_id,
    recipient=None,
    soft_delete=True
) -> None
```

**Arguments:**

- **notification_id** (`int`):
  The ID of the notification to delete.

- **recipient** (`Optional[UserModel]`):
  Optional user instance to filter the notification by recipient.

- **soft_delete** (`bool`):
  If `True`, the notification is soft-deleted (moved to `DeletedNotifications`). If `False`, the notification is permanently deleted (requires admin role).

**Returns:**

- None.

---

# Settings

This section outlines the available settings for configuring the `dj-notification-api` package. You can customize these settings in your Django project's `settings.py` file to tailor the behavior of the notification system to your needs.

## Example Settings

Below is an example configuration with default values:

```python
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
# DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS = [if not provided, gets USERNAME_FIELD and REQUIRED_FIELDS from user model]
DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS = "django_notification.api.serializers.UserSerializer"
DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS = "django_notification.api.serializers.group.GroupSerializer"
DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE = "30/minute"
DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE = "100/minute"
DJANGO_NOTIFICATION_API_THROTTLE_CLASS = "django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"
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
```

# Settings Overview

Below is a detailed description of each setting, so you can better understand and tweak them to fit your project's needs.

### `DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE`

**Type**: `bool`
**Default**: `True`
**Description**: Enables soft delete, allowing notifications to be excluded from API views without removing them from the database. If enabled, the `clear_activities` and `clear_notification` actions will be available in the `activities` API.

----

### `DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE`

**Type**: `bool`
**Default**: `False`
**Description**: Enables hard delete, allowing notifications to be permanently removed from the database. If enabled, the `delete_activities` and `delete_notification` actions will be available in the `activities` API.

----

### `DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION`

**Type**: `bool`
**Default**: `False`
**Description**: Controls whether the admin interface allows adding new notifications. Set this to `True` to enable Admin users to create new notifications.

----

### `DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION`

**Type**: `bool`
**Default**: `False`
**Description**: Controls whether the admin interface allows modifying existing notifications. Set this to `True` to allow Admin users to edit notifications.

----

### `DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION`

**Type**: `bool`
**Default**: `False`
**Description**: Controls whether the admin interface allows deleting notifications. Set this to `True` to enable Admin users to delete notifications.

----

### `DJANGO_NOTIFICATION_ADMIN_SITE_CLASS`

**Type**: `Optional[str]`
**Default**: `None`
**Description**: Optionally specifies A custom AdminSite class to apply on Admin interface. This allows for more customization on Admin interface, enabling you to apply your AdminSite class into `dj-notification-api` Admin interface.

----

### `DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS`

**Type**: `bool`
**Default**: `False`
**Description**: When set to `True`, API responses will include all notification fields. By default, only essential fields are returned.

----

### `DJANGO_NOTIFICATION_SERIALIZER_EXCLUDE_NULL_FIELDS`

**Type**: `bool`
**Default**: `False`
**Description**: When set to `True`, API responses will exclude any fields that it's value is `null`.

----

### `DJANGO_NOTIFICATION_API_ALLOW_LIST`

**Type**: `bool`
**Default**: `True`
**Description**: Allows the listing of notifications via the API. Set to `False` to disable this feature.

----

### `DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE`

**Type**: `bool`
**Default**: `True`
**Description**: Allows retrieving individual notifications via the API. Set to `False` to disable this feature.

----

### `DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS`

**Type**: `List[str]`
**Default**: `USERNAME_FIELD` and `REQUIRED_FIELDS` from user model
**Description**: Defines the fields to be included in the user serializer in API.

----

### `DJANGO_NOTIFICATION_USER_SERIALIZER_CLASS`

**Type**: `str`
**Default**: `"django_notification.api.serializers.UserSerializer"`
**Description**: Specifies the serializer class used for user objects in the API. Customize this if you need a different user serializer.

----

### `DJANGO_NOTIFICATION_GROUP_SERIALIZER_CLASS`

**Type**: `str`
**Default**: `"django_notification.api.serializers.group.GroupSerializer"`
**Description**: Specifies the serializer class used for group objects in the API. You can change this to use a different group serializer.

----

### `DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE`

**Type**: `str`
**Default**: `"30/minute"`
**Description**: Sets the throttle rate (requests per minute, hour or day) for authenticated users in the API.

----

### `DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE`

**Type**: `str`
**Default**: `"100/minute"`
**Description**: Sets the throttle rate (requests per minute, hour or day) for staff (Admin) users in the API.

----

### `DJANGO_NOTIFICATION_API_THROTTLE_CLASS`

**Type**: `str`
**Default**: `"django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"`
**Description**: Specifies the throttle class used to limit API requests. Customize this or set it to `None` if no throttling is needed or want to use rest_framework `DEFAULT_THROTTLE_CLASSES`.

----

### `DJANGO_NOTIFICATION_API_PAGINATION_CLASS`

**Type**: `str`
**Default**: `"django_notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"`
**Description**: Defines the pagination class used in the API. Customize this if you prefer a different pagination style or set to `None` to disable pagination.

----

### `DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS`

**Type**: `Optional[str]`
**Default**: `None`
**Description**: Optionally specifies an additional permission class to extend the base permission (`IsAuthenticated`) for the API. This allows for more fine-grained access control, enabling you to restrict API access to users with a specific permission, in addition to requiring authentication.

----

### `DJANGO_NOTIFICATION_API_PARSER_CLASSES`

**Type**: `List[str]`
**Default**:
```python
DJANGO_NOTIFICATION_API_PARSER_CLASSES = [
  "rest_framework.parsers.JSONParser",
  "rest_framework.parsers.MultiPartParser",
  "rest_framework.parsers.FormParser",
]
```
**Description**: Specifies the parsers used to handle API request data formats. You can modify this list to add your parsers or set `None` if no parser is needed.

---

### `DJANGO_NOTIFICATION_API_FILTERSET_CLASS`

**Type**: `Optional[str]`
**Default**: `None`

**Description**: Specifies the filter class for API queries. If you want to use this, you need to add `django_filters` to your `INSTALLED_APPS` and provide the path to the `NotificationFilter` class (`"django_notification.api.filters.notification_filter.NotificationFilter"`). Alternatively, you can use a custom filter class if needed.

In your `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "django_filters",
    # ...
]
```

and then apply this setting:

```python
# Apply in settings.py

DJANGO_NOTIFICATION_API_FILTERSET_CLASS = "django_notification.api.filters.notification_filter.NotificationFilter"
```

### `DJANGO_NOTIFICATION_API_ORDERING_FIELDS`
**Type**: `List[str]`
**Default**: `["id", "timestamp", "public"]`

**Description**: Specifies the fields available for ordering in API queries, allowing the API responses to be sorted by these fields. You can see all available fields [here](#all-available-fields).

---

### `DJANGO_NOTIFICATION_API_SEARCH_FIELDS`
**Type**: `List[str]`
**Default**: `["verb", "description"]`

**Description**: Specifies the fields that are searchable in the API, allowing users to filter results based on these fields.


## All Available Fields:

These are all fields that are available for searching, ordering, and filtering in the notifications API, along with their recommended usage:

- `id`: Unique identifier of the notification (orderable, filterable).
- `recipient`: The users receiving the notification (filterable).
- `group`: The groups receiving the notification (filterable).
- `verb`: The action associated with the notification (searchable).
- `description`: A description of the notification (searchable).
- `status`: Current status of the notification (filterable).
- `actor_content_type`: Content type of the actor object (filterable).
- `target_content_type`: Content type of the target object (filterable).
- `action_object_content_type`: Content type of the action object (filterable).
- `public`: Indicates if the notification is public (orderable, filterable).
- `timestamp`: The time when the notification was created (orderable, filterable).
- `link`: URL associated with the action (searchable).
- `data`: Additional metadata or attributes in JSON format (searchable).
- `seen_by`: Users who have seen the notification (filterable).

**Note**: Exercise caution when modifying search and ordering fields. Avoid using foreign key or joined fields (`recipient`, `group`, `all content_types`, `seen_by`) in **search fields**, as this may result in errors.

---

# Conclusion

We hope this documentation has provided a comprehensive guide to using and understanding the `dj-notification-api`. Whether you're setting up for the first time or diving deep into API customization, this document covers essential steps, configurations, and use cases to help you make the most of the package. For more clear documentation, customization options, and updates, please refer to the official documentation on [Read the Docs](https://dj-notification-api.readthedocs.io/).

### Final Notes:
- **Version Compatibility**: Ensure your project meets the compatibility requirements for both Django and Python versions.
- **API Integration**: The package is designed for flexibility, allowing you to customize many features based on your application's needs.
- **Contributions**: Contributions are welcome! Feel free to check out the [Contributing guide](CONTRIBUTING.md) for more details.

If you encounter any issues or have feedback, please reach out via our [GitHub Issues page](https://github.com/lazarus-org/dj-notification-api/issues).
