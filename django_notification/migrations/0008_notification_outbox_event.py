"""Add durable notification event outbox with leased retries."""

from django.db import migrations, models
import django.core.serializers.json
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0007_notification_categories_preferences"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationOutboxEvent",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("kind", models.CharField(max_length=64)),
                ("payload", models.JSONField(
                    encoder=django.core.serializers.json.DjangoJSONEncoder
                )),
                ("status", models.CharField(
                    max_length=12, default="PENDING",
                    choices=[
                        ("PENDING", "Pending"),
                        ("PROCESSING", "Processing"),
                        ("DELIVERED", "Delivered"),
                        ("FAILED", "Failed"),
                    ],
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("available_at", models.DateTimeField(
                    default=django.utils.timezone.now
                )),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("lease_token", models.UUIDField(blank=True, null=True)),
                ("leased_until", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "notification_outbox_event",
                "ordering": ("pk",),
            },
        ),
        migrations.AddIndex(
            model_name="notificationoutboxevent",
            index=models.Index(
                fields=("status", "available_at", "id"),
                name="djnotify_outbox_ready_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationoutboxevent",
            index=models.Index(
                fields=("status", "leased_until", "id"),
                name="djnotify_outbox_lease_idx",
            ),
        ),
    ]
