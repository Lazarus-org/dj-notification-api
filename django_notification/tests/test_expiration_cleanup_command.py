"""Opt-in retention cleanup should be safe, bounded, and auditable."""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from django_notification.models import (
    Notification,
    NotificationCreationKey,
    NotificationSeen,
)

pytestmark = pytest.mark.django_db


def create(user, *, days_ago, **kwargs):
    """Create a sent notification already expired by a chosen number of days."""
    return Notification.objects.create_notification(
        actor=user,
        verb="retention test",
        recipients=[user],
        is_sent=True,
        expires_at=timezone.now() - timedelta(days=days_ago),
        **kwargs,
    )


def test_command_dry_run_default_and_retention_cutoff(user: User):
    """A plain invocation only reports eligible records, never deletes them."""
    old = create(user, days_ago=40)
    young = create(user, days_ago=10)
    permanent = Notification.objects.create_notification(
        actor=user,
        verb="permanent",
        recipients=[user],
        is_sent=True,
    )
    out = StringIO()
    call_command("prune_expired_notifications", stdout=out)
    assert "DRY RUN: 1 notification(s)" in out.getvalue()
    assert set(Notification.objects.values_list("pk", flat=True)) == {
        old.pk,
        young.pk,
        permanent.pk,
    }


def test_explicit_execute_hard_deletes_cascading_state_and_creation_claim(
    user: User,
):
    """Global cleanup releases its creation key and removes associated state."""
    item = Notification.objects.create_notification(
        actor=user,
        verb="event",
        recipients=[user],
        is_sent=True,
        idempotency_key="retention:event",  # Created active for read-state setup.
    )
    item.mark_as_seen(user)
    Notification.objects.filter(pk=item.pk).update(
        expires_at=timezone.now() - timedelta(days=45)
    )
    recent = create(user, days_ago=4)
    output = StringIO()
    call_command(
        "prune_expired_notifications",
        "--execute",
        "--batch-size=1",
        stdout=output,
    )
    assert "Deleted 1 expired notification(s)" in output.getvalue()
    assert not Notification.objects.filter(pk=item.pk).exists()
    assert not NotificationSeen.objects.filter(notification_id=item.pk).exists()
    assert not NotificationCreationKey.objects.filter(key="retention:event").exists()
    assert Notification.objects.filter(pk=recent.pk).exists()


def test_command_multiple_batches_and_repeat_are_idempotent(user: User):
    """Keyset cleanup progresses through all eligible IDs without reprocessing."""
    for _ in range(5):
        create(user, days_ago=50)
    create(user, days_ago=1)
    output = StringIO()
    call_command(
        "prune_expired_notifications",
        "--execute",
        "--batch-size=2",
        stdout=output,
    )
    assert "Deleted 5 expired notification(s)" in output.getvalue()
    assert Notification.objects.count() == 1
    output = StringIO()
    call_command("prune_expired_notifications", "--execute", stdout=output)
    assert "Deleted 0 expired notification(s)" in output.getvalue()


def test_cleanup_rejects_unsafe_arguments(user: User):
    """Invalid retention windows and batch sizes never attempt a deletion."""
    create(user, days_ago=50)
    for args in (
        ("--execute", "--older-than-days=-1"),
        ("--execute", "--batch-size=0"),
        ("--execute", "--batch-size=1001"),
        ("--execute", "--database=unknown"),
    ):
        with pytest.raises(CommandError):
            call_command("prune_expired_notifications", *args)
    assert Notification.objects.count() == 1
