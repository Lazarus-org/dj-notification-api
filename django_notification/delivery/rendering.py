"""Optional, restricted category/channel/locale message rendering."""

from dataclasses import dataclass
from string import Template

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_notification.models.notification_template import (
    LOCALE_PATTERN,
    NotificationTemplate,
    validate_message_template,
)


@dataclass(frozen=True)
class RenderedMessage:
    """Transient text passed to a backend; never stored on delivery jobs."""

    subject: str
    body: str
    locale: str


def normalize_locale(value):
    """Accept ordinary language tags; reject arbitrary template selectors."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    return (
        normalized
        if len(normalized) <= 16 and LOCALE_PATTERN.fullmatch(normalized)
        else None
    )


def delivery_locale(recipient):
    """Prefer a conventional user language field, then deployment default."""
    value = (
        getattr(recipient, "notification_locale", None)
        or getattr(recipient, "language_preference", None)
        or getattr(recipient, "language_code", None)
    )
    default = getattr(
        settings,
        "DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE",
        settings.LANGUAGE_CODE,
    )
    resolved_default = normalize_locale(default)
    if resolved_default is None:
        raise ImproperlyConfigured("Invalid notification delivery default locale")
    return normalize_locale(value) or resolved_default


def _candidates(locale, default):
    """Try exact locale, base language, configured default and its base."""
    result = []
    for item in (locale, locale.split("-")[0], default, default.split("-")[0]):
        if item not in result:
            result.append(item)
    return result


def render_delivery(delivery):
    """Render a safe message or retain the Phase-14 fallback for no template.

    Use only five explicit scalar notification fields. Never resolve dotted attributes,
    display recipient details, or evaluate arbitrary expressions.

    """
    notification = delivery.notification
    category = notification.category
    locale = delivery_locale(delivery.recipient)
    default = normalize_locale(
        getattr(
            settings,
            "DJANGO_NOTIFICATION_DELIVERY_DEFAULT_LOCALE",
            settings.LANGUAGE_CODE,
        )
    )
    if default is None:
        raise ImproperlyConfigured("Invalid notification delivery default locale")

    templates = NotificationTemplate.objects.using(delivery._state.db).filter(
        category_id=notification.category_id,
        channel=delivery.channel,
        is_active=True,
        locale__in=_candidates(locale, default),
    )
    by_locale = {item.locale: item for item in templates}
    chosen = next(
        (by_locale[key] for key in _candidates(locale, default) if key in by_locale),
        None,
    )
    if chosen is None:
        text = notification.description or notification.verb
        if notification.link:
            text = f"{text}\n\n{notification.link}"
        return RenderedMessage(notification.verb, text, locale)

    values = {
        "verb": notification.verb or "",
        "description": notification.description or "",
        "link": notification.link or "",
        "category": category.name,
        "priority": notification.priority,
    }
    # Validate again: bulk updates can bypass model.clean().
    validate_message_template(chosen.subject)
    validate_message_template(chosen.body)
    if not chosen.body.strip():
        from django.core.exceptions import ValidationError

        raise ValidationError("Delivery template body cannot be blank")
    return RenderedMessage(
        subject=Template(chosen.subject or "$verb").substitute(values),
        body=Template(chosen.body).substitute(values),
        locale=chosen.locale,
    )
