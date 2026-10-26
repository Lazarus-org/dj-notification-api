"""Managed, locale-specific external notification message templates."""

import re
from string import Template

from django.core.exceptions import ValidationError
from django.db import models

TEMPLATE_CHANNELS = (
    ("email", "Email"),
    ("sms", "SMS"),
    ("push", "Push"),
)
TEMPLATE_VARIABLES = frozenset(
    (
        "verb",
        "description",
        "link",
        "category",
        "priority",
    )
)
LOCALE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")


def validate_message_template(value):
    """Reject malformed or unknown placeholders, including field traversals."""
    if not isinstance(value, str):
        raise ValidationError("A template must be text")
    for match in Template.pattern.finditer(value):
        identifier = match.group("named") or match.group("braced")
        if match.group("invalid") is not None or (
            identifier is not None and identifier not in TEMPLATE_VARIABLES
        ):
            raise ValidationError("Unsupported notification template placeholder")
    try:
        Template(value).substitute({key: "" for key in TEMPLATE_VARIABLES})
    except (KeyError, ValueError) as exc:
        raise ValidationError("Invalid notification template") from exc


class NotificationTemplate(models.Model):
    """One editable message definition per category/channel/locale.

    Template updates affect queued retries; providers must use delivery IDs for
    idempotency and deployers should version templates operationally.

    """

    category = models.ForeignKey(
        "django_notification.NotificationCategory",
        on_delete=models.CASCADE,
        related_name="delivery_templates",
    )
    channel = models.CharField(max_length=16, choices=TEMPLATE_CHANNELS)
    locale = models.CharField(max_length=16, default="en")
    subject = models.CharField(max_length=250, blank=True)
    body = models.TextField(max_length=8192)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_template"
        constraints = [
            models.UniqueConstraint(
                fields=("category", "channel", "locale"),
                name="djnotify_unique_template_locale",
            ),
        ]

    def clean(self):
        """Validate the locale and restricted interpolation vocabulary."""
        super().clean()
        if not isinstance(self.locale, str) or not LOCALE_PATTERN.fullmatch(
            self.locale
        ):
            raise ValidationError({"locale": "Use a normalized language tag"})
        for field in ("subject", "body"):
            try:
                validate_message_template(getattr(self, field))
            except ValidationError as exc:
                raise ValidationError({field: exc.messages}) from exc
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValidationError({"body": "Message body cannot be blank"})

    def __str__(self):
        """Identify the template without rendering notification content."""
        return f"{self.category_id}:{self.channel}:{self.locale}"
