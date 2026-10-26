# dj-notification-api

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

**dj-notification-api** provides a configurable notification inbox for Django and
Django REST Framework. Address a notification to users, Django groups, or both;
track each user's read and deleted state independently; and integrate optional
external delivery using pluggable email, SMS, push, or signed webhook backends.

**A Django application is all you need to start.** Redis, Celery, Django
Channels, and external delivery providers are not required for the inbox API.

## Features

- **Personal inbox:** unread/read lists, previews, summary counters, idempotent
  seen/unseen actions, and bulk operations.
- **Recipient isolation:** direct users and Django groups (dynamic membership or
  creation-time snapshot). Staff access never automatically widens personal visibility.
- **Lifecycle controls:** send state, expiration, deduplication/idempotency keys,
  safe per-user clearing, and managed notification categories/priorities.
- **Preferences:** per-category and per-channel controls, localized
  templates, quiet hours, and daily/weekly email digests.
- **Optional integrations:** post-commit lifecycle events, durable transactional
  outbox, authenticated Django Channels hints, provider-specific delivery jobs,
  configurable routing rules, and retry/recovery commands.
- **Operations:** aggregate queue health, failure diagnostics, historical
  delivery analytics, and Prometheus-compatible text export.

## Requirements

Supported environments are Python **3.10–3.14**, Django **5.2, 6.0, or 6.1**,
and Django REST Framework **3.18**. Python 3.10/3.11 use Django 5.2;
Django 6.x requires Python 3.12 or newer. The package also depends on
`django-filter`. See [compatibility and development](docs/development_toolchain.rst).

See the [upgrade guide](docs/upgrading.rst) when moving an existing application
to these framework requirements.

## Quick start

Install into your Django project:

```bash
pip install dj-notification-api
```

Add the package and DRF to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # Your Django apps ...
    "rest_framework",
    "django_notification",
]
```

Mount its API and apply the bundled migrations:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("notification/", include("django_notification.api.routers.notification")),
]
```

```bash
python manage.py migrate
```

Create a notification from trusted application code:

```python
from django.contrib.auth import get_user_model
from django_notification.models import Notification

User = get_user_model()
actor = User.objects.get(pk=1)
recipient = User.objects.get(pk=2)

Notification.objects.create_notification(
    actor=actor,
    verb="assigned a task",
    recipients=[recipient],
    description="A new task is ready for you.",
    is_sent=True,
)
```

An authenticated recipient can now access their inbox:

```http
GET /notification/notifications/
GET /notification/notifications/summary/
GET /notification/notifications/{id}/preview/
POST /notification/notifications/{id}/mark_seen/
GET /notification/activities/
```

These routes are **personal**, not an admin-wide notification listing. An
inaccessible or expired notification is not exposed. Detail GET is read-only by default. Legacy clients may explicitly enable
automatic read marking; `preview/` always leaves state unchanged. Read more in the [API guide](docs/api_guide.rst).

## Optional external delivery

To dispatch email or other external channels, enable the transactional outbox,
register the delivery event receiver, and run both workers:

```python
# settings.py
DJANGO_NOTIFICATION_API_EVENT_DELIVERY = "outbox"
DJANGO_NOTIFICATION_DELIVERY_BACKENDS = {
    "email": "django_notification.delivery.backends.DjangoEmailBackend",
}
```

```python
# Your application's apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "your_app"

    def ready(self):
        from django_notification.delivery import connect_notification_delivery

        connect_notification_delivery()
```

```bash
python manage.py process_notification_outbox --loop
python manage.py process_notification_deliveries --loop
```

Email uses Django's configured email backend and `DEFAULT_FROM_EMAIL`.
SMS and push require application-defined adapters; webhooks use the built-in
signed HTTPS adapter. Delivery is **at least once**: configure provider
idempotency and do not assume that queue acceptance proves delivery to an end
user. See [external delivery](docs/delivery.rst) and
[transactional outbox](docs/outbox.rst).

### Real-time WebSockets (optional)

```bash
pip install 'dj-notification-api[channels]'
# For a Redis-backed Channels layer:
pip install 'dj-notification-api[redis]'
```

The optional Channels adapter sends **notification IDs/event hints only**, not
notification contents. Connections must be authenticated, and clients should
re-fetch authorized notification data through the REST API. See
[Channels integration](docs/channels.rst) for ASGI configuration and registration.

## Documentation

| Guide | Contents |
| --- | --- |
| [Quick start](docs/quick_start.rst) | Install and follow a notification through read and clear actions |
| [Notification behavior](docs/concepts.rst) | Audiences, independent state, preferences and acknowledgements |
| [REST API](docs/api_guide.rst) | Endpoints, permissions, compatibility |
| [Models and usage](docs/usage.rst) | QuerySets, lifecycle, audience, expiry |
| [Configuration](docs/settings.rst) | Runtime settings, defaults and precedence |
| [Customization](docs/customization.rst) | Safe list serializers, permissions and filtersets |
| [Events and outbox](docs/events.rst) · [Outbox](docs/outbox.rst) | Commit behavior and durable retries |
| [Delivery](docs/delivery.rst) · [Templates](docs/templates_and_channels.rst) | Adapters, locales, preferences |
| [Schedules](docs/schedules_and_digests.rst) · [Routing](docs/routing_rules.rst) | Quiet hours, digests, rules |
| [Channels](docs/channels.rst) | Authenticated WebSockets |
| [Operations](docs/operations.rst) · [Analytics](docs/delivery_analytics.rst) | Monitoring, failure reports, trends |
| [Troubleshooting](docs/troubleshooting.rst) | Missing inbox items, stalled delivery, retries and sockets |
| [Upgrading](docs/upgrading.rst) | Framework changes, safe HTTP clients and migration steps |
| [Contributor guide](CONTRIBUTING.md) | uv, tox, local development |

Full documentation: <https://dj-notification-api.readthedocs.io/en/latest/>.

## Security

- Use authenticated API access and keep notification creation in trusted code.
- Group visibility is re-evaluated for dynamic audiences; snapshot audiences
  retain recipients resolved at creation.
- GET is read-only by default. Use POST/DELETE for state changes, with CSRF
  protection for session-authenticated requests. See the [API guide](docs/api_guide.rst).
- Do not store secrets in message text or provider logs. External jobs persist
  identifiers and sanitized outcomes, not a durable content audit trail.
- For security reports, see [SECURITY.md](SECURITY.md).

## Development and contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md),
[the changelog](CHANGELOG.md), and the
[issue tracker](https://github.com/lazarus-org/dj-notification-api/issues).

## License

MIT — see [LICENCE](LICENCE).

## Upgrading

This source requires Python 3.10+ and Django 5.2+. GET requests are read-only
by default; migrate state changes to POST/DELETE. Legacy clients can explicitly
set `DJANGO_NOTIFICATION_API_ALLOW_LEGACY_GET_MUTATIONS=True` and
`DJANGO_NOTIFICATION_API_RETRIEVE_MARKS_SEEN=True` temporarily, accepting the
CSRF risk of mutating GET requests. See [settings](https://dj-notification-api.readthedocs.io/en/latest/settings.html).
Follow the [upgrade guide](docs/upgrading.rst) for client migration and database checks.
