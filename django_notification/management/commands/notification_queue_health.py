"""Read-only notification worker health for operations and monitoring."""

import json

from django.core.management.base import BaseCommand, CommandError

from django_notification.operations.health import (
    evaluate_queue_health,
    notification_queue_health,
    prometheus_queue_metrics,
)


class Command(BaseCommand):
    """Report aggregate health, optionally exit nonzero on warning."""

    help = "Read-only notification queue metrics (text, JSON or Prometheus)."

    def add_arguments(self, parser):
        """Keep optional health thresholds explicit and provider-free."""
        parser.add_argument("--database", default="default")
        format_group = parser.add_mutually_exclusive_group()
        format_group.add_argument("--json", action="store_true")
        format_group.add_argument("--prometheus", action="store_true")
        parser.add_argument("--max-ready", type=int, default=1000)
        parser.add_argument("--max-oldest-seconds", type=int, default=900)
        parser.add_argument("--max-failed", type=int, default=100)
        parser.add_argument("--max-stranded", type=int, default=0)
        parser.add_argument("--fail-on-unhealthy", action="store_true")

    def handle(self, *args, **options):
        """Never output recipient or event metadata in any format."""
        try:
            snapshot = notification_queue_health(options["database"])
            verdict = evaluate_queue_health(
                snapshot,
                max_ready=options["max_ready"],
                max_oldest_seconds=options["max_oldest_seconds"],
                max_failed=options["max_failed"],
                max_stranded=options["max_stranded"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if options["prometheus"]:
            self.stdout.write(prometheus_queue_metrics(snapshot), ending="")
        elif options["json"]:
            self.stdout.write(json.dumps({**snapshot, **verdict}, sort_keys=True))
        else:
            self.stdout.write(f"notification_queue_healthy={int(verdict['healthy'])}")
            for name, queue in snapshot["queues"].items():
                self.stdout.write(
                    f"{name} "
                    + " ".join(f"{key}={value}" for key, value in queue.items())
                )
            self.stdout.write(
                f"digest_child_pending={snapshot['digest_child_pending']}"
            )
            for item in verdict["violations"]:
                self.stdout.write(
                    f"ALERT {item['queue']} {item['metric']}={item['value']} "
                    f"threshold={item['threshold']}"
                )
        if options["fail_on_unhealthy"] and not verdict["healthy"]:
            raise CommandError("Notification queue thresholds exceeded")
