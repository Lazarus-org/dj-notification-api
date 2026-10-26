"""Explicit operator recovery for terminally failed notification events."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone

from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)


class Command(BaseCommand):
    """Requeue failed rows by ID, never delivered or in-flight rows."""

    help = "Requeue specific FAILED notification outbox event IDs."

    def add_arguments(self, parser):
        """Require explicit operator input to avoid uncontrolled replays."""
        parser.add_argument("ids", nargs="+", type=int)
        parser.add_argument("--database", default="default")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        """Requeue only confirmed failed records and reset their attempts."""
        alias = options["database"]
        if alias not in connections:
            raise CommandError("Unknown database alias")
        ids = set(options["ids"])
        if not ids or any(pk < 1 for pk in ids):
            raise CommandError("Event IDs must be positive integers")
        matching = NotificationOutboxEvent.objects.using(alias).filter(
            pk__in=ids, status=OutboxStatus.FAILED
        )
        if options["dry_run"]:
            self.stdout.write(
                f"Would requeue {matching.count()} failed outbox event(s)"
            )
            return
        updated = matching.update(
            status=OutboxStatus.PENDING,
            attempts=0,
            available_at=timezone.now(),
            failed_at=None,
            lease_token=None,
            leased_until=None,
        )
        self.stdout.write(f"Requeued {updated} failed outbox event(s)")
