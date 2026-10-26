"""Explicit maintenance for previously delivered notification outbox rows."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone

from django_notification.models.notification_outbox_event import (
    NotificationOutboxEvent,
    OutboxStatus,
)


class Command(BaseCommand):
    """Delete only acknowledged events after the operator's retention period."""

    help = "Preview or delete old DELIVERED outbox events (dry run by default)."

    def add_arguments(self, parser):
        """Expose explicit destructive switch and bounded batch size."""
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--older-than-days", type=int, default=30)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--database", default="default")

    def handle(self, *args, **options):
        """Leave all pending, processing and terminal-failed rows untouched."""
        days = options["older_than_days"]
        size = options["batch_size"]
        alias = options["database"]
        if days < 0:
            raise CommandError("--older-than-days must be nonnegative")
        if not 1 <= size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000")
        if alias not in connections:
            raise CommandError("Unknown database alias")
        cutoff = timezone.now() - timedelta(days=days)
        base = NotificationOutboxEvent.objects.using(alias).filter(
            status=OutboxStatus.DELIVERED, delivered_at__lte=cutoff
        )
        if not options["execute"]:
            self.stdout.write(f"DRY RUN: {base.count()} delivered events eligible")
            return
        max_pk = base.order_by("-pk").values_list("pk", flat=True).first()
        last_pk = 0
        count = 0
        if max_pk is not None:
            while True:
                with transaction.atomic(using=alias):
                    ids = list(
                        base.filter(pk__gt=last_pk, pk__lte=max_pk)
                        .order_by("pk")
                        .values_list("pk", flat=True)[:size]
                    )
                    if not ids:
                        break
                    last_pk = ids[-1]
                    removed, _ = base.filter(pk__in=ids).delete()
                    count += removed
        self.stdout.write(f"Pruned {count} delivered outbox events")
