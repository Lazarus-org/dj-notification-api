from django_notification.tests import setup
import copy

import pytest
from django.core.cache import cache
from django_notification.tests.fixtures import (
    admin_user,
    another_user,
    deleted_notification,
    group,
    group_with_perm,
    notification,
    notification_dict,
    notification_recipient,
    notification_seen,
    notifications,
    permission,
    qs_group,
    qs_user,
    user,
    user_content_type,
)


__all__ = (
    "setup",
    "admin_user",
    "another_user",
    "deleted_notification",
    "group",
    "group_with_perm",
    "notification",
    "notification_dict",
    "notification_recipient",
    "notification_seen",
    "notifications",
    "permission",
    "qs_group",
    "qs_user",
    "user",
    "user_content_type",
)


@pytest.fixture(autouse=True)
def isolated_runtime_state():
    """DB rollback does not reset the throttle cache or mutable config singleton."""
    from django_notification.settings.conf import config

    original = copy.deepcopy(vars(config))
    cache.clear()
    yield
    cache.clear()
    vars(config).clear()
    vars(config).update(original)


@pytest.fixture(autouse=True)
def migration_seed_data(request):
    """Restore data-migration defaults after transactional tests flush the DB."""
    if request.node.get_closest_marker("django_db") or any(
        name in request.fixturenames for name in ("db", "transactional_db")
    ):
        request.getfixturevalue("db")
        from django_notification.models import NotificationCategory

        NotificationCategory.objects.get_or_create(
            slug="general",
            defaults={"name": "General"},
        )
