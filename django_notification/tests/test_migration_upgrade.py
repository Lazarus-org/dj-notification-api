"""Preserve legacy audience/read state across an upgrade and reverse migration."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_upgrade_from_last_shipped_schema_and_reverse(user):
    old = [
        ("django_notification", "0002_alter_deletednotification_deleted_at_and_more")
    ]
    latest = [("django_notification", "0012_notification_routing_rules")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        content_type = apps.get_model("contenttypes", "ContentType").objects.get(
            app_label="auth", model="user"
        )
        item = apps.get_model("django_notification", "Notification").objects.create(
            verb="Legacy",
            actor_content_type_id=content_type.pk,
            actor_object_id=user.pk,
            is_sent=True,
        )
        apps.get_model("django_notification", "NotificationRecipient").objects.create(
            notification_id=item.pk, recipient_id=user.pk
        )
        apps.get_model("django_notification", "NotificationSeen").objects.create(
            notification_id=item.pk, user_id=user.pk
        )
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        apps = executor.loader.project_state(latest).apps
        upgraded = apps.get_model("django_notification", "Notification").objects.get(
            pk=item.pk
        )
        assert upgraded.category_id == "general"
        assert upgraded.priority == "NORMAL"
        assert upgraded.group_audience_mode == "DYNAMIC"
        assert upgraded.expires_at is None
        assert (
            apps.get_model("django_notification", "NotificationRecipient")
            .objects.filter(notification_id=item.pk, recipient_id=user.pk)
            .exists()
        )
        assert (
            apps.get_model("django_notification", "NotificationSeen")
            .objects.filter(notification_id=item.pk, user_id=user.pk)
            .exists()
        )
        executor = MigrationExecutor(connection)
        executor.migrate(old)
        apps = executor.loader.project_state(old).apps
        assert (
            apps.get_model("django_notification", "Notification")
            .objects.get(pk=item.pk)
            .is_sent
        )
    finally:
        MigrationExecutor(connection).migrate(latest)
