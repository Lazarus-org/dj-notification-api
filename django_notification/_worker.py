"""Shared, bounded worker retry/lease primitives.

These helpers intentionally do not perform receiver or provider I/O. Each worker owns
its external side effects and lease-token acknowledgements.

"""

from django.db import transaction

EXHAUSTED_SWEEP_LIMIT = 500


def validate_retry_settings(max_attempts, lease_seconds, base_seconds, maximum_seconds):
    """Validate the common, bounded configuration for leased workers."""
    if not 1 <= max_attempts <= 100:
        raise ValueError("max_attempts must be between 1 and 100")
    if not 5 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be between 5 and 3600")
    if not 1 <= base_seconds <= maximum_seconds <= 86400:
        raise ValueError("Invalid retry delay bounds")


def retry_delay_seconds(attempt, base_seconds, maximum_seconds):
    """Return capped exponential backoff for a one-based claim count."""
    return min(maximum_seconds, base_seconds * (2 ** min(max(attempt - 1, 0), 30)))


# The shared worker helper accepts explicit keyword-only retry/lease inputs.
# pylint: disable-next=too-many-arguments
def fail_exhausted_claims(
    rows, *, ready, attempt_field, max_attempts, failed_status, now, database
):
    """Fail at most one page of due claims that have used their retry budget.

    Selecting IDs under a short transaction bounds the update and the number of locks,
    even when millions of expired claims accumulate. The conditional UPDATE rechecks
    readiness and retry count so a claim renewed by a different worker cannot be
    overwritten with FAILED.

    """
    exhausted = {f"{attempt_field}__gte": max_attempts}
    with transaction.atomic(using=database):
        ids = list(
            rows.filter(ready, **exhausted)
            .order_by("pk")
            .values_list("pk", flat=True)[:EXHAUSTED_SWEEP_LIMIT]
        )
        if not ids:
            return 0
        return (
            rows.filter(pk__in=ids)
            .filter(ready, **exhausted)
            .update(
                status=failed_status,
                failed_at=now,
                lease_token=None,
                leased_until=None,
            )
        )
