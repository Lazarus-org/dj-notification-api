"""Lint package migrations without requiring an ignored host Django project."""

import os
import sys
from pathlib import Path

import django
from django.core.management import call_command
from django_migration_linter.management.commands.lintmigrations import Command


def main():
    """Check model drift and run the original configured migration linter."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "django_notification.tests.typing_settings"
    )
    django.setup()
    call_command("makemigrations", "django_notification", check=True, dry_run=True)
    call_command(Command(), "django_notification")


if __name__ == "__main__":
    main()
