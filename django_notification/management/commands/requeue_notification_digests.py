"""Explicit recovery of terminally failed digest email envelopes."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone

from django_notification.models.notification_delivery import (
    DeliveryStatus,
    NotificationDelivery,
)
from django_notification.models.notification_digest import NotificationDigest


class Command(BaseCommand):
    """Requeue only failed envelopes and their failed child jobs."""

    help = "Requeue failed notification digest IDs (may resend on retries)."

    def add_arguments(self, parser):
        """Require explicit selected IDs rather than mass requeueing."""
        parser.add_argument("ids", nargs="+", type=int)
        parser.add_argument("--database", default="default")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        """Reset retry state atomically and retain delivery history."""
        ids = options["ids"]
        if any(pk <= 0 for pk in ids) or len(ids) > 500:
            raise CommandError("Pass between 1 and 500 positive digest IDs")
        using = options["database"]
        if using not in connections:
            raise CommandError("Unknown database alias")
        if options["dry_run"]:
            eligible = (
                NotificationDigest.objects.using(using)
                .filter(
                    pk__in=ids,
                    status=DeliveryStatus.FAILED,
                )
                .count()
            )
            self.stdout.write(f"Would requeue {eligible} failed digests")
            return
        with transaction.atomic(using=using):
            rows = NotificationDigest.objects.using(using)
            failed = list(
                rows.select_for_update()
                .filter(
                    pk__in=ids,
                    status=DeliveryStatus.FAILED,
                )
                .values_list("pk", flat=True)
            )
            NotificationDelivery.objects.using(using).filter(
                digest_id__in=failed,
                status=DeliveryStatus.FAILED,
            ).update(status=DeliveryStatus.PENDING, failed_at=None)
            updated = rows.filter(pk__in=failed).update(
                status=DeliveryStatus.PENDING,
                available_at=timezone.now(),
                attempts=0,
                failed_at=None,
                lease_token=None,
                leased_until=None,
            )
        self.stdout.write(f"requeued={updated}")
