"""Historical, redacted delivery reports for trusted Django operators."""

import csv
import json
from io import StringIO

from django.core.management.base import BaseCommand, CommandError

from django_notification.operations.analytics import notification_delivery_analytics

_CSV_COLUMNS = (
    "dimension",
    "key",
    "total",
    "pending",
    "processing",
    "delivered",
    "failed",
    "cancelled",
    "terminal_jobs",
    "terminal_success_rate_percent",
    "retried_jobs",
    "average_queue_latency_seconds",
    "maximum_queue_latency_seconds",
)


class Command(BaseCommand):
    """Report existing delivery records, without any side effects."""

    help = "Read-only historical delivery analytics; no recipient data."

    def add_arguments(self, parser):
        """Expose bounded cohorts and aggregate-only export formats."""
        parser.add_argument("--database", default="default")
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--category-limit", type=int, default=10)
        output = parser.add_mutually_exclusive_group()
        output.add_argument("--json", action="store_true")
        output.add_argument("--csv", action="store_true")

    def handle(self, *args, **options):
        """Never display recipient, payload, title or provider-error fields."""
        try:
            result = notification_delivery_analytics(
                database=options["database"],
                days=options["days"],
                category_limit=options["category_limit"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if options["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
            return
        if options["csv"]:
            stream = StringIO()
            writer = csv.DictWriter(stream, fieldnames=_CSV_COLUMNS)
            writer.writeheader()
            for dimension, records in (
                ("overall", [{"key": "all", **result["overall"]}]),
                ("channel", result["by_channel"]),
                ("category", result["by_category"]),
                ("priority", result["by_priority"]),
            ):
                for record in records:
                    writer.writerow(
                        {
                            **{name: record.get(name) for name in _CSV_COLUMNS},
                            "dimension": dimension,
                        }
                    )
            self.stdout.write(stream.getvalue(), ending="")
            return
        window = result["window"]
        self.stdout.write(
            f"Delivery jobs created {window['start']} through {window['end']} "
            "(UTC, end exclusive)"
        )
        for name, record in (("overall", result["overall"]),):
            self.stdout.write(
                f"{name} total={record['total']} delivered={record['delivered']} "
                f"failed={record['failed']} pending={record['pending']} "
                f"processing={record['processing']} cancelled={record['cancelled']} "
                f"terminal_success_pct={record['terminal_success_rate_percent']} "
                f"avg_queue_latency_seconds={record['average_queue_latency_seconds']}"
            )
        for dimension in ("channel", "category", "priority"):
            for record in result[f"by_{dimension}"]:
                self.stdout.write(
                    f"{dimension}={record['key']} total={record['total']} "
                    f"delivered={record['delivered']} failed={record['failed']} "
                    f"terminal_success_pct={record['terminal_success_rate_percent']}"
                )
        self.stdout.write(f"attempt_outcomes={result['attempt_outcomes']}")
        self.stdout.write(f"job_claim_distribution={result['job_claim_distribution']}")
        self.stdout.write(
            f"queue_latency_distribution={result['queue_latency_distribution']}"
        )
