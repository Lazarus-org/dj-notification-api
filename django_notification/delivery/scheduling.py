"""Pure timezone-aware quiet-hour and digest scheduling functions."""

from datetime import datetime, timedelta
from datetime import timezone as utc_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.utils import timezone

from django_notification.models.notification_delivery_schedule import DeliveryFrequency


def valid_zone(value):
    """Allow only installed IANA zone names; never accept untrusted tz offsets."""
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValidationError("A valid IANA timezone is required")
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError, KeyError) as exc:
        raise ValidationError("Unknown IANA timezone") from exc


def _wall(date, at, zone):
    """Normalize a local wall time through UTC across DST gaps."""
    local = datetime.combine(date, at).replace(tzinfo=zone)
    return local.astimezone(utc_timezone.utc).astimezone(zone)


def _wall_candidates(date, at, zone):
    """Include both folds at DST fall-back; use the next valid gap time."""
    naive = datetime.combine(date, at)
    results = []
    for fold in (0, 1):
        local = naive.replace(tzinfo=zone, fold=fold)
        utc = local.astimezone(utc_timezone.utc)
        normalized = utc.astimezone(zone)
        if normalized.replace(tzinfo=None) == naive:
            results.append(utc)
    if results:
        return sorted(set(results))
    # A spring-forward gap has no real matching wall time. Do not bring
    # delivery forward into the unavailable hour or previous quiet period.
    normalized_candidates = [
        naive.replace(tzinfo=zone, fold=fold)
        .astimezone(utc_timezone.utc)
        .astimezone(zone)
        for fold in (0, 1)
    ]
    future = [
        item for item in normalized_candidates if item.replace(tzinfo=None) > naive
    ]
    chosen = min(future) if future else max(normalized_candidates)
    return [chosen.astimezone(utc_timezone.utc)]


def quiet_end_at(now, setting):
    """Return the next safe delivery instant, or now outside quiet hours."""
    start, end = setting.quiet_start, setting.quiet_end
    if start is None or end is None or start == end:
        return now
    zone = valid_zone(setting.timezone)
    local = now.astimezone(zone)
    clock = local.timetz().replace(tzinfo=None)
    if start < end:
        within = start <= clock < end
        day = local.date()
    else:
        within = clock >= start or clock < end
        day = local.date() + (timedelta(days=1) if clock >= start else timedelta())
    if not within:
        return now
    for _ in range(3):
        for candidate in _wall_candidates(day, end, zone):
            if candidate > now:
                return candidate
        day += timedelta(days=1)
    return _wall(day, end, zone).astimezone(utc_timezone.utc)


def next_digest_at(now, setting):
    """The next 09:00 local day or Monday; never a past digest slot."""
    zone = valid_zone(setting.timezone)
    local = now.astimezone(zone)
    if setting.frequency == DeliveryFrequency.DAILY:
        day = local.date() + timedelta(days=1)
    elif setting.frequency == DeliveryFrequency.WEEKLY:
        days = (7 - local.weekday()) % 7 or 7
        day = local.date() + timedelta(days=days)
    else:
        raise ValueError("This schedule does not request a digest")
    slot = _wall(day, datetime.min.time().replace(hour=9), zone)
    slot = slot.astimezone(utc_timezone.utc)
    # Allow quiet hours to shift delivery, but not the digest identity/slot.
    return slot


def schedule_for(notification, setting, now=None):
    """Return (digest slot or None, next permissible send instant)."""
    now = now or timezone.now()
    if (
        setting is None
        or notification.category.is_mandatory
        or (notification.priority == "URGENT")
    ):
        return None, now
    if setting.frequency != DeliveryFrequency.IMMEDIATE:
        slot = next_digest_at(now, setting)
        return slot, quiet_end_at(slot, setting)
    return None, quiet_end_at(now, setting)
