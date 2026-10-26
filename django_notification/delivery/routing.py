"""Deterministic server-side rules for selecting external delivery channels.

Rules alter delivery, not notification visibility, content, priority, or the recipient's
channel preferences. No rules means all configured channels.

"""

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from django_notification.models.helper.enums.status_choices import NotificationStatus
from django_notification.models.notification_channel_preference import CHANNEL_VALUES
from django_notification.models.notification_routing_rule import (
    PRIORITY_RANK,
    NotificationRoutingRule,
    RoutingAction,
)


def routed_channels(notification, configured_channels, database="default"):
    """Return the eligible configured channels for one notification.

    A rule may only manipulate channels that are already configured. Global rules are
    applied before category-specific rules at the same sort order; later rules can
    intentionally override earlier choices. Bad persisted rules fail closed rather than
    silently widening an external audience.

    """
    channels = tuple(configured_channels)
    configured = set(channels)
    if not configured <= CHANNEL_VALUES:
        raise ImproperlyConfigured("Unsupported configured delivery channel")
    rank = PRIORITY_RANK.get(notification.priority)
    if rank is None:
        raise ImproperlyConfigured("Invalid notification priority")
    records = NotificationRoutingRule.objects.using(database).filter(
        Q(category_id__isnull=True) | Q(category_id=notification.category_id),
        enabled=True,
    )
    selected = set(configured)
    ordered = sorted(
        records,
        key=lambda rule: (
            rule.sort_order,
            rule.category_id is not None,
            rule.pk,
        ),
    )
    valid_statuses = {entry.value for entry in NotificationStatus}
    for rule in ordered:
        if rule.notification_status and rule.notification_status not in valid_statuses:
            raise ImproperlyConfigured("Invalid persisted routing status")
        low = PRIORITY_RANK.get(rule.min_priority)
        high = PRIORITY_RANK.get(rule.max_priority)
        if low is None or high is None or low > high:
            raise ImproperlyConfigured("Invalid persisted routing priority")
        if rank < low or rank > high:
            continue
        if rule.notification_status and (
            rule.notification_status != notification.status
        ):
            continue
        values = rule.channels
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(item, str) for item in values)
            or len(values) != len(set(values))
            or not set(values) <= CHANNEL_VALUES
        ):
            raise ImproperlyConfigured("Invalid persisted routing channels")
        allowed = set(values) & configured
        if rule.action == RoutingAction.REPLACE:
            selected = allowed
        elif rule.action == RoutingAction.ADD:
            selected |= allowed
        elif rule.action == RoutingAction.REMOVE:
            selected -= allowed
        else:
            raise ImproperlyConfigured("Invalid persisted routing action")
    return tuple(channel for channel in channels if channel in selected)
