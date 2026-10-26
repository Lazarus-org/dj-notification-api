"""Run independent, retryable external notification deliveries."""

import time

from django.core.management.base import BaseCommand, CommandError

from django_notification.delivery.service import NotificationDeliveryService


class Command(BaseCommand):
    """Process one bounded batch or poll continuously."""

    help = "Process due external delivery jobs and scheduled email digests."

    def add_arguments(self, parser):
        """Expose lease/retry tuning without requiring Celery or Redis."""
        parser.add_argument("--database", default="default")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--max-attempts", type=int, default=5)
        parser.add_argument("--lease-seconds", type=int, default=60)
        parser.add_argument("--retry-base-seconds", type=int, default=5)
        parser.add_argument("--retry-max-seconds", type=int, default=3600)
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        """Print counts only; never expose addresses or provider details."""
        interval = options["poll_seconds"]
        if not 0.1 <= interval <= 3600:
            raise CommandError("--poll-seconds must be between 0.1 and 3600")
        try:
            service = NotificationDeliveryService(
                database=options["database"],
                max_attempts=options["max_attempts"],
                lease_seconds=options["lease_seconds"],
                retry_base_seconds=options["retry_base_seconds"],
                retry_max_seconds=options["retry_max_seconds"],
            )
            while True:
                counts = service.process_batch(limit=options["batch_size"])
                self.stdout.write(
                    " ".join(f"{key}={value}" for key, value in counts.items())
                )
                if not options["loop"]:
                    break
                if not any(counts.values()):
                    time.sleep(interval)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except KeyboardInterrupt:
            self.stdout.write("Notification delivery worker stopped")
