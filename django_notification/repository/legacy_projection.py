"""Compatibility-only projections for the pre-composable manager selectors.

New callers should serialize model instances, not rely on projected dicts. This adapter
intentionally lives outside ``NotificationQuerySet`` so the query implementation is
independent of HTTP response field configuration.

"""

from typing import TYPE_CHECKING

from django.db.models import QuerySet

from django_notification.constants.default_settings import default_serializer_settings

if TYPE_CHECKING:
    from django_notification.repository.queryset.notification import (
        NotificationQuerySet,
    )


def legacy_notification_projection(
    queryset: "NotificationQuerySet", display_detail: bool
) -> QuerySet:
    """Keep historical ``display_detail`` return types for legacy selectors.

    False returns a ``values()`` queryset using the original compact fields; True
    returns notification instances with detail relationships prefetched.

    """
    if display_detail:
        return queryset.with_related()
    return queryset.values(*default_serializer_settings.notification_serializer_fields)
