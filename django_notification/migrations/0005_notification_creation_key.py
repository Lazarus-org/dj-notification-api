"""Persist event identity and time-window deduplication claims."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0004_notification_group_audience_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationCreationKey",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("kind", models.CharField(
                    max_length=13,
                    choices=[
                        ("IDEMPOTENCY", "Idempotent creation"),
                        ("DEDUPLICATION", "Time-window deduplication"),
                    ],
                )),
                ("key", models.CharField(max_length=200)),
                ("request_fingerprint", models.CharField(
                    max_length=64, blank=True,
                )),
                ("expires_at", models.DateTimeField(
                    null=True, blank=True, db_index=True,
                )),
                ("notification", models.ForeignKey(
                    to="django_notification.notification",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="creation_keys", null=True, blank=True,
                )),
            ],
            options={"db_table": "notification_creation_key"},
        ),
        migrations.AddConstraint(
            model_name="notificationcreationkey",
            constraint=models.UniqueConstraint(
                fields=["kind", "key"],
                name="unique_notification_creation_key",
            ),
        ),
    ]
