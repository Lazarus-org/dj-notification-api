"""Enable opt-in frozen group recipients without changing legacy targeting."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0003_alter_notificationseen_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="group_audience_mode",
            field=models.CharField(
                choices=[
                    ("DYNAMIC", "Current group membership"),
                    ("SNAPSHOT", "Members captured at creation"),
                ],
                default="DYNAMIC",
                help_text=(
                    "DYNAMIC follows current group membership; SNAPSHOT retains "
                    "the group members captured when created through the manager."
                ),
                max_length=8,
                verbose_name="Group audience mode",
            ),
        ),
    ]
