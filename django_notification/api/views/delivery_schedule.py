"""Authenticated, personal delivery cadence and quiet-hour controls."""

from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from django_notification.delivery.scheduling import valid_zone
from django_notification.models.notification_channel_preference import (
    CHANNEL_CHOICES,
    CHANNEL_VALUES,
)
from django_notification.models.notification_delivery_schedule import (
    DeliveryFrequency,
    NotificationDeliverySchedule,
)


# Input-only serializer; the action persists validated schedule values.
# pylint: disable-next=abstract-method
class DeliveryScheduleSerializer(serializers.Serializer):
    """Narrow public contract; never accept user IDs or worker-owned fields."""

    frequency = serializers.ChoiceField(choices=DeliveryFrequency.choices)
    timezone = serializers.CharField(max_length=64)
    quiet_start = serializers.TimeField(allow_null=True, required=False)
    quiet_end = serializers.TimeField(allow_null=True, required=False)

    def validate_timezone(self, value):
        """Require an installed IANA zone name."""
        try:
            valid_zone(value)
        except Exception as exc:
            raise serializers.ValidationError("Unknown IANA timezone") from exc
        return value

    def validate(self, attrs):
        """Require a matching start and end and email-only digests."""
        instance = None if self.context.get("replace") else self.instance
        channel = self.context["channel"]
        frequency = attrs.get(
            "frequency",
            instance.frequency if instance else DeliveryFrequency.IMMEDIATE,
        )
        if frequency != DeliveryFrequency.IMMEDIATE and channel != "email":
            raise serializers.ValidationError(
                {
                    "frequency": "Digests are supported for email only",
                }
            )
        start = attrs.get("quiet_start", instance.quiet_start if instance else None)
        end = attrs.get("quiet_end", instance.quiet_end if instance else None)
        if (start is None) != (end is None):
            raise serializers.ValidationError(
                {
                    "quiet_start": "Both quiet-hour boundaries are required",
                }
            )
        return attrs


def schedule_data(channel, obj):
    """Return a stable effective configuration, even without a DB override."""
    return {
        "channel": channel,
        "frequency": obj.frequency if obj else DeliveryFrequency.IMMEDIATE,
        "timezone": obj.timezone if obj else "UTC",
        "quiet_start": obj.quiet_start.isoformat() if obj and obj.quiet_start else None,
        "quiet_end": obj.quiet_end.isoformat() if obj and obj.quiet_end else None,
    }


class NotificationDeliveryScheduleActionsMixin:
    """Expose only the authenticated user's own scheduling preferences."""

    @action(detail=False, methods=["get"], url_path="delivery_schedule")
    def delivery_schedule(self, request):
        """Return effective settings for all known external channels."""
        alias = request.user._state.db or "default"
        settings = {
            item.channel: item
            for item in NotificationDeliverySchedule.objects.using(alias).filter(
                user=request.user
            )
        }
        return Response(
            [
                schedule_data(channel, settings.get(channel))
                for channel, _ in CHANNEL_CHOICES
            ]
        )

    @action(
        detail=False,
        methods=["put", "patch"],
        url_path=r"delivery_schedule/(?P<channel>[a-z]+)",
    )
    def set_delivery_schedule(self, request, channel=None):
        """Update one channel atomically, without affecting other users."""
        if channel not in CHANNEL_VALUES:
            raise NotFound("Unknown notification delivery channel")
        alias = request.user._state.db or "default"
        with transaction.atomic(using=alias):
            existing = (
                NotificationDeliverySchedule.objects.using(alias)
                .filter(
                    user=request.user,
                    channel=channel,
                )
                .first()
            )
            serializer = DeliveryScheduleSerializer(
                existing,
                data=request.data,
                partial=request.method == "PATCH",
                context={"channel": channel, "replace": request.method == "PUT"},
            )
            serializer.is_valid(raise_exception=True)
            values = dict(serializer.validated_data)
            if request.method == "PUT":
                values = {"quiet_start": None, "quiet_end": None, **values}
            if existing is None:
                defaults = {
                    "frequency": DeliveryFrequency.IMMEDIATE,
                    "timezone": "UTC",
                    "quiet_start": None,
                    "quiet_end": None,
                }
                defaults.update(values)
                item, _ = NotificationDeliverySchedule.objects.using(
                    alias
                ).update_or_create(
                    user=request.user,
                    channel=channel,
                    defaults=defaults,
                )
            else:
                item, _ = NotificationDeliverySchedule.objects.using(
                    alias
                ).update_or_create(
                    user=request.user,
                    channel=channel,
                    defaults=values,
                )
        return Response(schedule_data(channel, item))
