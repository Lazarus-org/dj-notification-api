"""Explicit manual recovery for failed per-channel delivery jobs."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone

from django_notification.models.notification_delivery import (
    DeliveryStatus,
    NotificationDelivery,
)


class Command(BaseCommand):
    """Requeue only FAILED jobs without erasing their attempt history."""

    help = "Requeue specific FAILED external notification delivery IDs."

    def add_arguments(self, parser):
        """Require explicit IDs and an optional database alias."""
        parser.add_argument("ids", nargs="+", type=int)
        parser.add_argument("--database", default="default")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        """Reset the retry budget, not the monotonic attempt counter."""
        alias = options["database"]
        if alias not in connections:
            raise CommandError("Unknown database alias")
        ids = set(options["ids"])
        if any(item < 1 for item in ids):
            raise CommandError("Delivery IDs must be positive")
        matching = NotificationDelivery.objects.using(alias).filter(
            pk__in=ids,
            status=DeliveryStatus.FAILED,
        )
        if options["dry_run"]:
            self.stdout.write(f"Would requeue {matching.count()} failed deliveries")
            return
        count = matching.update(
            status=DeliveryStatus.PENDING,
            retry_attempts=0,
            failed_at=None,
            available_at=timezone.now(),
            lease_token=None,
            leased_until=None,
        )
        self.stdout.write(f"Requeued {count} failed deliveries")
