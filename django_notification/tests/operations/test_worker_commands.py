"""Verify operator entry points reject bad configuration and stop cleanly."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "command", ["process_notification_outbox", "process_notification_deliveries"]
)
@pytest.mark.parametrize(
    "options",
    [
        {"batch_size": 0},
        {"batch_size": 1001},
        {"poll_seconds": 0},
        {"database": "unknown"},
        {"max_attempts": 0},
        {"lease_seconds": 4},
    ],
)
def test_worker_command_rejects_invalid_configuration(command, options):
    with pytest.raises(CommandError):
        call_command(command, stdout=StringIO(), **options)


@pytest.mark.parametrize(
    "command", ["process_notification_outbox", "process_notification_deliveries"]
)
def test_worker_command_bounded_pass_and_interrupt(command):
    output = StringIO()
    call_command(command, batch_size=1, stdout=output)
    assert "delivered=0" in output.getvalue()
    module = f"django_notification.management.commands.{command}"
    with patch(f"{module}.time.sleep", side_effect=KeyboardInterrupt) as sleep:
        call_command(command, loop=True, poll_seconds=0.1, stdout=output)
    sleep.assert_called_once_with(0.1)
    assert "worker stopped" in output.getvalue()
