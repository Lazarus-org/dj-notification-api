"""Add managed categories, priorities, and per-user opt-out preferences."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_general_category(apps, schema_editor):
    """Create the default category before adding its non-null FK."""
    Category = apps.get_model("django_notification", "NotificationCategory")
    Category.objects.using(schema_editor.connection.alias).get_or_create(
        slug="general",
        defaults={
            "name": "General",
            "is_mandatory": False,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0006_notification_expires_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationCategory",
            fields=[
                ("slug", models.SlugField(max_length=64, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("is_mandatory", models.BooleanField(
                    default=False,
                    help_text="Mandatory categories cannot be disabled by users.",
                )),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "notification_category",
                "verbose_name": "Notification category",
                "verbose_name_plural": "Notification categories",
                "ordering": ("slug",),
            },
        ),
        migrations.RunPython(seed_general_category, migrations.RunPython.noop),
        migrations.AddField(
            model_name="notification",
            name="category",
            field=models.ForeignKey(
                default="general",
                help_text="Managed category key; general is the default.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="notifications",
                to="django_notification.notificationcategory",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="priority",
            field=models.CharField(
                max_length=8,
                default="NORMAL",
                db_index=True,
                choices=[
                    ("LOW", "Low"), ("NORMAL", "Normal"),
                    ("HIGH", "High"), ("URGENT", "Urgent"),
                ],
                help_text="Display priority independent of notification status.",
            ),
        ),
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="preferences",
                    to="django_notification.notificationcategory",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="notification_preferences",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "notification_preference",
                "verbose_name": "Notification preference",
                "verbose_name_plural": "Notification preferences",
            },
        ),
        migrations.AddConstraint(
            model_name="notificationpreference",
            constraint=models.UniqueConstraint(
                fields=("user", "category"),
                name="unique_notification_preference_user_category",
            ),
        ),
    ]
