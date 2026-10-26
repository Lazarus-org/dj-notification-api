"""Optional database-backed routing rules for external delivery."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("django_notification", "0011_delivery_schedules_digests"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationRoutingRule",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("name", models.CharField(max_length=100)),
                ("enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("min_priority", models.CharField(
                    choices=[("LOW", "Low"), ("NORMAL", "Normal"),
                             ("HIGH", "High"), ("URGENT", "Urgent")],
                    default="LOW", max_length=8,
                )),
                ("max_priority", models.CharField(
                    choices=[("LOW", "Low"), ("NORMAL", "Normal"),
                             ("HIGH", "High"), ("URGENT", "Urgent")],
                    default="URGENT", max_length=8,
                )),
                ("notification_status", models.CharField(
                    blank=True, null=True, max_length=15, choices=[
                        ("ERROR", "Error - Indicates critical errors that require immediate attention"),
                        ("SUCCESS", "Success - Indicates successful completion of an operation"),
                        ("WARNING", "Warning - Indicates potential issues or concerns that should be addressed"),
                        ("INFO", "Information - Provides general informational messages"),
                        ("CRITICAL", "Critical - Indicates critical issues that may impact functionality"),
                        ("SENSITIVE", "Sensitive - Indicates notifications related to sensitive data"),
                        ("INFRASTRUCTURE", "Infrastructure - Indicates notifications related to system infrastructure"),
                    ],
                    help_text="Leave empty to match any notification status.",
                )),
                ("action", models.CharField(
                    max_length=7, choices=[
                        ("REPLACE", "Use only these channels"),
                        ("ADD", "Add these channels"),
                        ("REMOVE", "Remove these channels"),
                    ],
                )),
                ("channels", models.JSONField(default=list)),
                ("category", models.ForeignKey(
                    to="django_notification.notificationcategory", null=True,
                    blank=True, related_name="routing_rules",
                    on_delete=django.db.models.deletion.CASCADE,
                )),
            ],
            options={
                "db_table": "notification_routing_rule",
                "ordering": ("sort_order", "pk"),
            },
        ),
        migrations.AddIndex(
            model_name="notificationroutingrule",
            index=models.Index(
                fields=("enabled", "category", "sort_order"),
                name="djnotify_routing_lookup_idx",
            ),
        ),
    ]
