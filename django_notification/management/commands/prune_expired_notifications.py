"""Explicit, bounded hard deletion of notifications past their retention window."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils import timezone

from django_notification.models.notification import Notification


class Command(BaseCommand):
    """Prune expired notifications only when an operator enables execution.

    Each bounded delete cascades to group/recipient links, per-user state and creation
    keys. The command intentionally has no implicit scheduler.

    """

    help = (
        "Preview or hard-delete expired notifications older than a retention "
        "period (default: dry run, 30 days after expiration)."
    )

    def add_arguments(self, parser):
        """Expose explicit execution and controlled retention settings."""
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually hard-delete eligible records (dry run by default).",
        )
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=30,
            metavar="DAYS",
            help="Days to retain expired records before deletion (default: 30).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            metavar="N",
            help="Maximum notification rows deleted per transaction (1–1000).",
        )
        parser.add_argument(
            "--database",
            default="default",
            metavar="ALIAS",
            help="Django database alias to operate on (default: default).",
        )

    def handle(self, *args, **options):
        """Freeze a cutoff and a high-water ID, deleting in finite keyset batches."""
        days = options["older_than_days"]
        size = options["batch_size"]
        alias = options["database"]
        if days < 0:
            raise CommandError("--older-than-days must be nonnegative")
        if not 1 <= size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000")
        if alias not in connections:
            raise CommandError(f"Unknown database alias: {alias}")

        cutoff = timezone.now() - timedelta(days=days)
        base = Notification.objects.using(alias).expired_at(cutoff)
        if not options["execute"]:
            count = base.count()
            self.stdout.write(
                f"DRY RUN: {count} notification(s) would be removed "
                f"(expires_at <= {cutoff.isoformat()}, database={alias})."
            )
            return

        # New notifications created while the command runs cannot extend the
        # job beyond this high-water mark. Recheck expiration under row locks
        # inside each batch so extensions made before locking are respected.
        max_pk = base.order_by("-pk").values_list("pk", flat=True).first()
        removed = 0
        last_pk = 0
        if max_pk is not None:
            while True:
                with transaction.atomic(using=alias):
                    batch = list(
                        base.filter(pk__gt=last_pk, pk__lte=max_pk)
                        .order_by("pk")
                        .select_for_update()
                        .values_list("pk", flat=True)[:size]
                    )
                    if not batch:
                        break
                    last_pk = batch[-1]
                    # Expires_at could have been changed while selecting;
                    # retain the eligibility filter on the delete queryset.
                    eligible = base.filter(pk__in=batch)
                    current = eligible.count()
                    eligible.delete()
                    removed += current
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {removed} expired notification(s) "
                f"(expires_at <= {cutoff.isoformat()}, database={alias})."
            )
        )
