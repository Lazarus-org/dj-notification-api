"""Optional external delivery templates and per-user channel opt-outs."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0009_external_notification_delivery"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationTemplate",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("channel", models.CharField(
                    choices=[
                        ("email", "Email"), ("sms", "SMS"), ("push", "Push"),
                    ], max_length=16,
                )),
                ("locale", models.CharField(max_length=16, default="en")),
                ("subject", models.CharField(max_length=250, blank=True)),
                ("body", models.TextField(max_length=8192)),
                ("is_active", models.BooleanField(default=True)),
                ("category", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="delivery_templates",
                    to="django_notification.notificationcategory",
                )),
            ],
            options={"db_table": "notification_template"},
        ),
        migrations.AddConstraint(
            model_name="notificationtemplate",
            constraint=models.UniqueConstraint(
                fields=("category", "channel", "locale"),
                name="djnotify_unique_template_locale",
            ),
        ),
        migrations.CreateModel(
            name="NotificationChannelPreference",
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
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="channel_preferences",
                    to="django_notification.notificationcategory",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_channel_preferences",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "notification_channel_preference"},
        ),
        migrations.AddConstraint(
            model_name="notificationchannelpreference",
            constraint=models.UniqueConstraint(
                fields=("user", "category", "channel"),
                name="djnotify_unique_channel_preference",
            ),
        ),
    ]
