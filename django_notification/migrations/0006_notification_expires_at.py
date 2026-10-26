"""Optional notification expiration; null preserves all existing records."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0005_notification_creation_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    "Optional expiration instant after which this notification no "
                    "longer appears in personal inboxes; database retention "
                    "is separate."
                ),
                null=True,
                verbose_name="Expires at",
            ),
        ),
    ]
