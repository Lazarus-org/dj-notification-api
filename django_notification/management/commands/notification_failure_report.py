"""Inspect recent worker failures without exposing notification content."""

import json

from django.core.management.base import BaseCommand, CommandError

from django_notification.operations.failures import notification_failure_report


class Command(BaseCommand):
    """Read-only operational diagnostics with opt-in bounded job identities."""

    help = "Show recent terminal failures and sanitized backend result codes."

    def add_arguments(self, parser):
        """Limit both the observation window and any printed job identities."""
        parser.add_argument("--database", default="default")
        parser.add_argument("--since-hours", type=int, default=24)
        parser.add_argument("--show-ids", action="store_true")
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        """Reveal only requested queue IDs and allowlisted failure codes."""
        try:
            report = notification_failure_report(
                database=options["database"],
                since_hours=options["since_hours"],
                show_ids=options["show_ids"],
                limit=options["limit"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if options["json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
            return
        for name, counts in report["terminal_failures"].items():
            self.stdout.write(f"{name} failed={counts['count']}")
            if "job_ids" in counts:
                self.stdout.write(
                    f"{name} job_ids={','.join(str(pk) for pk in counts['job_ids'])}"
                )
        for entry in report["attempt_codes"]:
            self.stdout.write(f"attempt_code={entry['code']} count={entry['count']}")
