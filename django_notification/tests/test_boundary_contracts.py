"""Regression contracts for validation, compatibility APIs and operator output."""

from datetime import datetime, timezone
from io import StringIO
import runpy
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Q
from django.http import Http404
from django.test import override_settings

from django_notification.admin.preference import NotificationCategoryAdmin
from django_notification.delivery.preferences import channel_enabled
from django_notification.events import NotificationEvent, publish_notification_event
from django_notification.integrations.channels import audience
from django_notification.models import Notification, NotificationCategory
from django_notification.models.permissions.notification_permission import (
    NotificationPermission,
)
from django_notification.operations.failures import notification_failure_report
from django_notification.operations.health import notification_queue_health
from django_notification.services.notification import NotificationLifecycleService
from django_notification.settings.checks import check_notification_settings
from django_notification.tests.delivery.test_templates_preferences import _delivery

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "name,args,options",
    [
        ("prune_notification_outbox", [], {"older_than_days": -1}),
        ("prune_notification_outbox", [], {"batch_size": 0}),
        ("prune_notification_outbox", [], {"database": "missing"}),
        ("requeue_notification_outbox", [0], {}),
        ("requeue_notification_outbox", [1], {"database": "missing"}),
        ("requeue_notification_deliveries", [0], {}),
        ("requeue_notification_deliveries", [1], {"database": "missing"}),
        ("requeue_notification_digests", [0], {}),
        ("requeue_notification_digests", list(range(1, 502)), {}),
        ("requeue_notification_digests", [1], {"database": "missing"}),
        ("notification_failure_report", [], {"since_hours": 0}),
    ],
)
def test_commands_reject_invalid_operator_arguments(name, args, options):
    with pytest.raises(CommandError):
        call_command(name, *args, stdout=StringIO(), **options)


def test_operator_text_reports_are_redacted(user):
    delivery = _delivery(user)
    delivery.status = "FAILED"
    delivery.failed_at = datetime.now(timezone.utc)
    delivery.save()
    delivery.attempt_history.create(number=1, status="FAILED", code="temporary_failure")
    for command in ("notification_delivery_report", "notification_failure_report"):
        output = StringIO()
        options = {"show_ids": True} if command == "notification_failure_report" else {}
        call_command(command, stdout=output, **options)
        text = output.getvalue()
        assert "failed=1" in text
        assert user.email not in text
        assert delivery.notification.verb not in text
        if options:
            assert "job_ids=" in text
            assert "attempt_code=temporary_failure count=1" in text
        else:
            assert "channel=email" in text


def test_operations_validate_database_and_time_arguments():
    for function in (notification_failure_report, notification_queue_health):
        with pytest.raises(ValueError, match="database"):
            function(database="missing")
    for hours in (0, 8761, "24"):
        with pytest.raises(ValueError, match="since_hours"):
            notification_failure_report(since_hours=hours)
    for now in (datetime(2026, 1, 1), "today"):
        with pytest.raises(ValueError, match="aware"):
            notification_queue_health(now=now)


def test_system_checks_validate_optional_backend_and_locale_settings():
    backend = {"email": "django_notification.delivery.backends.DjangoEmailBackend"}
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS=backend):
        assert "django_notification.E002" in {
            error.id for error in check_notification_settings(None)
        }
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_BACKENDS={"email": "bad.path"}):
        assert "django_notification.E003" in {
            error.id for error in check_notification_settings(None)
        }
    with override_settings(DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE="../bad"):
        assert "django_notification.E004" in {
            error.id for error in check_notification_settings(None)
        }


def test_invalid_event_mode_cannot_silently_drop_event():
    with override_settings(DJANGO_NOTIFICATION_API_EVENT_DELIVERY="bad"):
        with pytest.raises(ValueError, match="Unsupported"):
            publish_notification_event(
                NotificationEvent(kind="test", database="default")
            )


def test_category_admin_freezes_existing_primary_key():
    model_admin = NotificationCategoryAdmin(NotificationCategory, admin.site)
    assert model_admin.get_readonly_fields(None) == ()
    assert model_admin.get_readonly_fields(
        None, NotificationCategory(slug="general")
    ) == ("slug",)


@pytest.mark.parametrize(
    "module,class_name,values,expected",
    [
        (
            "notification_channel_preference",
            "NotificationChannelPreference",
            {"channel": "email"},
            "None:email",
        ),
        ("notification_creation_key", "NotificationCreationKey", {}, ""),
        (
            "notification_delivery",
            "NotificationDelivery",
            {"id": 9, "channel": "email"},
            "Delivery #9 (email: PENDING)",
        ),
        (
            "notification_delivery",
            "NotificationDeliveryAttempt",
            {"number": 2, "status": "RETRY"},
            "Attempt #2 (RETRY)",
        ),
        ("notification_digest", "NotificationDigest", {}, ""),
        ("notification_outbox_event", "NotificationOutboxEvent", {}, ""),
        ("notification_preference", "NotificationPreference", {}, ""),
        (
            "notification_routing_rule",
            "NotificationRoutingRule",
            {"name": "Operations"},
            "Operations",
        ),
        (
            "notification_template",
            "NotificationTemplate",
            {"channel": "email", "locale": "en"},
            "",
        ),
        (
            "notification_delivery_schedule",
            "NotificationDeliverySchedule",
            {"channel": "email"},
            "Delivery schedule (email)",
        ),
    ],
)
def test_model_labels_omit_personal_information(module, class_name, values, expected):
    from importlib import import_module

    model = getattr(import_module("django_notification.models." + module), class_name)
    label = str(model(**values))
    assert isinstance(label, str) and label
    if expected:
        assert label == expected
    assert "@" not in label


def test_legacy_queryset_mutations_still_delegate(user):
    queryset = Notification.objects.all()
    with pytest.warns(DeprecationWarning):
        notification = queryset.create_notification(
            "Legacy", user, recipients=[user], is_sent=True
        )
    with pytest.warns(DeprecationWarning):
        queryset.update_notification(notification.pk, public=False)
    notification.refresh_from_db()
    assert not notification.public
    with pytest.warns(DeprecationWarning):
        assert queryset.mark_all_as_seen(user) == 1
    assert queryset.seen(user, conditions=Q(pk=notification.pk)).count() == 1
    assert queryset.unseen(user, conditions=Q(pk=notification.pk)).count() == 0
    with pytest.warns(DeprecationWarning):
        queryset.clear_all(user)
    assert list(queryset.deleted()) == [notification]
    assert list(queryset.deleted(user)) == [notification]
    with pytest.warns(DeprecationWarning):
        queryset.delete_notification(notification.pk, soft_delete=False)
    assert not queryset.exists()


def test_query_targeting_accepts_unevaluated_queryset(user):
    delivery = _delivery(user)
    assert list(
        Notification.objects.targeted_to(
            recipients=type(user).objects.filter(pk=user.pk)
        )
    ) == [delivery.notification]


def test_invalid_personal_identity_never_selects_or_changes_rows():
    queryset = Notification.objects.all()
    service = NotificationLifecycleService(queryset)
    assert not queryset.deleted_by(None).exists()
    assert not service._personal_records(None).exists()
    assert service.mark_all_as_seen(None) == 0
    assert service.clear_all(None) is None
    assert not NotificationPermission(Notification()).user_has_permission(None)


@pytest.mark.parametrize("identity", [None, "bad", [], 0, -1])
def test_seen_rejects_malformed_identifiers(user, identity):
    service = NotificationLifecycleService(Notification.objects.all())
    with pytest.raises(Http404):
        service.set_seen(user, identity, True)


@pytest.mark.parametrize("ids", [[], list(range(501))])
def test_bulk_mutations_reject_unbounded_or_empty_selection(user, ids):
    service = NotificationLifecycleService(Notification.objects.all())
    for action in (
        lambda: service.set_many_seen(user, ids, True),
        lambda: service.clear_selected(user, ids),
    ):
        with pytest.raises(ValueError, match="between 1 and 500"):
            action()


def test_creation_identity_validation(user):
    service = NotificationLifecycleService(Notification.objects.all())
    for obj in (object(), type(user)()):
        with pytest.raises(ValueError, match="persisted"):
            service._model_identity(obj)
    for target in (type(user)(), True, object()):
        with pytest.raises(ValueError):
            service._target_ids([target])
    assert service._target_ids([3, "2", 3]) == ["2", "3"]
    for category in (None, 4, ""):
        with pytest.raises(ValueError, match="category"):
            service.create_notification("Test", user, category=category)
    with override_settings(USE_TZ=False):
        with pytest.raises(ValueError, match="naive"):
            service.create_notification(
                "Test", user, expires_at=datetime.now(timezone.utc)
            )


def test_snapshot_requires_group_metadata_and_handles_empty_groups(user, group):
    service = NotificationLifecycleService(Notification.objects.all())
    notification = Notification.objects.create_notification(
        "Empty group", user, groups=[group]
    )
    service._snapshot_group_recipients(notification)
    assert not notification.recipient.exists()
    for value in (FieldDoesNotExist(), SimpleNamespace()):
        options = (
            {"side_effect": value}
            if isinstance(value, Exception)
            else {"return_value": value}
        )
        with patch.object(type(user)._meta, "get_field", **options):
            with pytest.raises(ValueError, match="groups M2M"):
                service._snapshot_group_recipients(notification)


def test_direct_visibility_survives_missing_group_metadata(user):
    delivery = _delivery(user)
    original = type(user)._meta.get_field

    def lookup(name):
        if name == "groups":
            raise FieldDoesNotExist
        return original(name)

    with patch.object(type(user)._meta, "get_field", side_effect=lookup):
        assert list(Notification.objects.visible_to(user)) == [delivery.notification]
        assert list(
            audience.eligible_audience(delivery.notification_id, "default")
        ) == [user.pk]
    field = type(user)._meta.get_field("groups")
    with patch.object(field.remote_field, "through", None):
        with pytest.raises(ValueError, match="through"):
            list(audience.eligible_audience(delivery.notification_id, "default"))


def test_missing_category_disables_delivery(user):
    assert not channel_enabled(user.pk, "missing", "email", "default")


@pytest.mark.parametrize(
    "module",
    [
        "django_notification.repository.legacy_projection",
        "django_notification.repository.manager.notification",
        "django_notification.repository.queryset.notification",
        "django_notification.utils.user_model",
    ],
)
def test_static_annotation_imports_resolve_to_real_models(module):
    # Evaluate annotation imports in an isolated namespace, without replacing
    # application modules or Django's model registry.
    from importlib.util import find_spec

    with patch("typing.TYPE_CHECKING", True):
        namespace = runpy.run_path(find_spec(module).origin)
    expected = (
        "UserModel"
        if module.endswith("user_model")
        else (
            "NotificationQuerySet"
            if module.endswith("legacy_projection")
            else "Notification"
        )
    )
    assert namespace[expected].__module__.startswith("django")
