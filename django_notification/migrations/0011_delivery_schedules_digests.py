"""Per-channel delivery schedules, email digests, and job association."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0010_notification_templates_channels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDeliverySchedule",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("channel", models.CharField(
                    choices=[
                        ("email", "Email"), ("sms", "SMS"),
                        ("push", "Push"), ("webhook", "Webhook"),
                    ], max_length=16,
                )),
                ("frequency", models.CharField(
                    max_length=9, default="IMMEDIATE", choices=[
                        ("IMMEDIATE", "Immediately"),
                        ("DAILY", "Daily email digest"),
                        ("WEEKLY", "Weekly email digest"),
                    ],
                )),
                ("timezone", models.CharField(max_length=64, default="UTC")),
                ("quiet_start", models.TimeField(blank=True, null=True)),
                ("quiet_end", models.TimeField(blank=True, null=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_delivery_schedules",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "notification_delivery_schedule"},
        ),
        migrations.AddConstraint(
            model_name="notificationdeliveryschedule",
            constraint=models.UniqueConstraint(
                fields=("user", "channel"),
                name="djnotify_unique_delivery_schedule",
            ),
        ),
        migrations.CreateModel(
            name="NotificationDigest",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("channel", models.CharField(default="email", max_length=16)),
                ("scheduled_at", models.DateTimeField()),
                ("status", models.CharField(
                    max_length=12, default="PENDING", choices=[
                        ("PENDING", "Pending"),
                        ("PROCESSING", "Processing"),
                        ("DELIVERED", "Delivered"),
                        ("FAILED", "Failed"),
                        ("CANCELLED", "Cancelled"),
                    ],
                )),
                ("available_at", models.DateTimeField(
                    default=django.utils.timezone.now,
                )),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("leased_until", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("recipient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_digests",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "notification_digest"},
        ),
        migrations.AddConstraint(
            model_name="notificationdigest",
            constraint=models.UniqueConstraint(
                fields=("recipient", "channel", "scheduled_at"),
                name="djnotify_unique_digest_slot",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdigest",
            index=models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_digest_ready_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdigest",
            index=models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_digest_lease_idx",
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="digest",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="deliveries", to="django_notification.notificationdigest",
            ),
        ),
    ]
