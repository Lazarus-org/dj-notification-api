"""Optional durable external delivery jobs and sanitized attempt history."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0008_notification_outbox_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("channel", models.CharField(max_length=16)),
                ("status", models.CharField(
                    max_length=12, default="PENDING",
                    choices=[
                        ("PENDING", "Pending"),
                        ("PROCESSING", "Processing"),
                        ("DELIVERED", "Delivered"),
                        ("FAILED", "Failed"),
                        ("CANCELLED", "Cancelled"),
                    ],
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("available_at", models.DateTimeField(
                    default=django.utils.timezone.now,
                )),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("retry_attempts", models.PositiveIntegerField(default=0)),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("leased_until", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("notification", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="external_deliveries",
                    to="django_notification.notification",
                )),
                ("recipient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="external_notification_deliveries",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "notification_delivery"},
        ),
        migrations.CreateModel(
            name="NotificationDeliveryAttempt",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("number", models.PositiveIntegerField()),
                ("status", models.CharField(
                    max_length=12,
                    choices=[
                        ("SUCCEEDED", "Succeeded"),
                        ("RETRY", "Retry scheduled"),
                        ("FAILED", "Permanent failure"),
                    ],
                )),
                ("code", models.CharField(max_length=48)),
                ("completed_at", models.DateTimeField(
                    default=django.utils.timezone.now,
                )),
                ("delivery", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attempt_history",
                    to="django_notification.notificationdelivery",
                )),
            ],
            options={
                "db_table": "notification_delivery_attempt",
                "ordering": ("-number",),
            },
        ),
        migrations.AddConstraint(
            model_name="notificationdelivery",
            constraint=models.UniqueConstraint(
                fields=("notification", "recipient", "channel"),
                name="djnotify_unique_delivery_target_channel",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_deliv_ready_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_deliv_lease_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationdeliveryattempt",
            constraint=models.UniqueConstraint(
                fields=("delivery", "number"),
                name="djnotify_unique_delivery_attempt",
            ),
        ),
    ]
