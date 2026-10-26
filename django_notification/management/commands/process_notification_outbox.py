"""Poll and deliver notification events persisted in the transactional outbox."""

import time

from django.core.management.base import BaseCommand, CommandError

from django_notification.outbox import OutboxDeliveryService


class Command(BaseCommand):
    """Run a bounded pass by default, or an operator-controlled polling loop."""

    help = (
        "Deliver pending notification outbox events. Requires configured "
        "notification_event receivers in this worker process."
    )

    def add_arguments(self, parser):
        """Allow explicit scheduling and bounded lease/retry configuration."""
        parser.add_argument("--database", default="default")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--max-attempts", type=int, default=5)
        parser.add_argument("--lease-seconds", type=int, default=60)
        parser.add_argument("--retry-base-seconds", type=int, default=5)
        parser.add_argument("--retry-max-seconds", type=int, default=3600)
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Poll continuously until interrupted (default: one pass).",
        )
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        """Do not emit event IDs, recipient data, or exception messages."""
        size = options["batch_size"]
        interval = options["poll_seconds"]
        if not 1 <= size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000")
        if not 0.1 <= interval <= 3600:
            raise CommandError("--poll-seconds must be between 0.1 and 3600")
        try:
            service = OutboxDeliveryService(
                database=options["database"],
                max_attempts=options["max_attempts"],
                lease_seconds=options["lease_seconds"],
                retry_base_seconds=options["retry_base_seconds"],
                retry_max_seconds=options["retry_max_seconds"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        try:
            while True:
                result = service.process_batch(limit=size)
                total = sum(result.values())
                self.stdout.write(
                    f"processed={total} delivered={result['delivered']} "
                    f"retry={result['retry']} failed={result['failed']} "
                    f"lost_lease={result['lost_lease']}"
                )
                if not options["loop"]:
                    break
                if total == 0:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Notification outbox worker stopped")
