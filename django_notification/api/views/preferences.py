"""Self-service category preferences and optional inbox field filters."""

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.serializers import BooleanField, Serializer

from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.models.notification_category import NotificationCategory
from django_notification.models.notification_channel_preference import (
    CHANNEL_CHOICES,
    CHANNEL_VALUES,
    NotificationChannelPreference,
)
from django_notification.models.notification_preference import NotificationPreference


# Input-only serializer; the action owns the preference write.
# pylint: disable-next=abstract-method
class PreferenceUpdateSerializer(Serializer):
    """Require a proper JSON boolean; never accept arbitrary profile fields."""

    enabled = BooleanField(required=True)


def filter_personal_notifications(queryset, request):
    """Apply optional inbox category/priority filters without widening scope."""
    category = request.query_params.get("category")
    if category:
        queryset = queryset.in_category(category)
    priority = request.query_params.get("priority")
    if priority:
        if priority not in NotificationPriority.values:
            raise ValidationError({"priority": "Unsupported priority"})
        queryset = queryset.with_priority(priority)
    return queryset


def _category_data(category, override=None):
    """Produce a privacy-safe category preference for the current user."""
    return {
        "category": category.pk,
        "name": category.name,
        "mandatory": category.is_mandatory,
        "enabled": bool(category.is_mandatory or override is None or override.enabled),
    }


class NotificationPreferenceActionsMixin:
    """Personal category catalog and user-owned preference mutation actions."""

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        """List selectable active categories without other users' preferences."""
        categories = NotificationCategory.objects.filter(is_active=True)
        return Response(
            [
                {
                    "category": item.pk,
                    "name": item.name,
                    "mandatory": item.is_mandatory,
                }
                for item in categories
            ]
        )

    @action(detail=False, methods=["get"], url_path="preferences")
    def preferences(self, request):
        """List effective preferences; missing override defaults to enabled."""
        overrides = {
            row.category_id: row
            for row in NotificationPreference.objects.filter(user=request.user)
        }
        categories = NotificationCategory.objects.filter(is_active=True)
        return Response(
            [
                _category_data(category, overrides.get(category.pk))
                for category in categories
            ]
        )

    @action(
        detail=False,
        methods=["put", "patch"],
        url_path=r"preferences/(?P<category_slug>[-a-zA-Z0-9_]+)",
    )
    def set_preference(self, request, category_slug=None):
        """Change one optional category without affecting other users."""
        serializer = PreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enabled = serializer.validated_data["enabled"]
        using = NotificationPreference.objects.db
        with transaction.atomic(using=using):
            # Lock category configuration during this preference update.
            category = (
                NotificationCategory.objects.using(using)
                .select_for_update()
                .filter(pk=category_slug, is_active=True)
                .first()
            )
            if category is None:
                raise NotFound("Unknown or inactive category")
            if category.is_mandatory and not enabled:
                raise ValidationError(
                    {"enabled": "This category is mandatory and cannot be disabled"}
                )
            preferences = NotificationPreference.objects.using(using)
            if enabled:
                # No override means enabled. Resetting avoids redundant rows.
                preferences.filter(user=request.user, category=category).delete()
            else:
                preferences.update_or_create(
                    user=request.user,
                    category=category,
                    defaults={"enabled": False},
                )
        override = (
            NotificationPreference.objects.using(using)
            .filter(user=request.user, category=category)
            .first()
        )
        return Response(_category_data(category, override))


class NotificationChannelPreferenceActionsMixin:
    """Authenticated self-service overrides for external delivery channels."""

    @action(detail=False, methods=["get"], url_path="channel_preferences")
    def channel_preferences(self, request):
        """Show effective preferences without exposing other users' records."""
        overrides = {
            (row.category_id, row.channel): row.enabled
            for row in NotificationChannelPreference.objects.using(
                request.user._state.db or "default"
            ).filter(user=request.user)
        }
        categories = NotificationCategory.objects.filter(is_active=True)
        return Response(
            [
                {
                    "category": category.pk,
                    "channel": channel,
                    "mandatory": category.is_mandatory,
                    "enabled": (
                        category.is_mandatory
                        or overrides.get((category.pk, channel), True)
                    ),
                }
                for category in categories
                for channel, _ in CHANNEL_CHOICES
            ]
        )

    @action(
        detail=False,
        methods=["put", "patch"],
        url_path=(
            r"channel_preferences/"
            r"(?P<category_slug>[-a-zA-Z0-9_]+)/(?P<channel>[a-z]+)"
        ),
    )
    def set_channel_preference(self, request, category_slug=None, channel=None):
        """Set this user's per-channel override, never another user's."""
        if channel not in CHANNEL_VALUES:
            raise NotFound("Unknown notification delivery channel")
        serializer = PreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enabled = serializer.validated_data["enabled"]
        using = request.user._state.db or NotificationChannelPreference.objects.db
        with transaction.atomic(using=using):
            category = (
                NotificationCategory.objects.using(using)
                .select_for_update()
                .filter(pk=category_slug, is_active=True)
                .first()
            )
            if category is None:
                raise NotFound("Unknown or inactive category")
            if category.is_mandatory and not enabled:
                raise ValidationError(
                    {"enabled": "Mandatory categories cannot be disabled"}
                )
            rows = NotificationChannelPreference.objects.using(using)
            if enabled:
                rows.filter(
                    user=request.user, category=category, channel=channel
                ).delete()
            else:
                rows.update_or_create(
                    user=request.user,
                    category=category,
                    channel=channel,
                    defaults={"enabled": False},
                )
        return Response(
            {
                "category": category.pk,
                "channel": channel,
                "mandatory": category.is_mandatory,
                "enabled": True if (category.is_mandatory) else enabled,
            }
        )
