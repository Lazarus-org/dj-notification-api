"""Best-effort notification lifecycle events emitted after database commit.

Connect to ``notification_event`` with Django's standard signal API. Receivers should
re-fetch data and enforce authorization for their delivery channel. Events are not a
durable outbox or a transactional messaging guarantee.

"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)


# One stable signal, one immutable payload contract. Subscribers can branch on
# ``event.kind`` without registering a separate signal for each operation.
class NotificationSignal(Signal):
    """Keep Django's robust dispatch without logging private receiver errors."""

    def _log_robust_failure(self, receiver, err):
        # Django's default implementation includes the exception and traceback,
        # both of which can contain provider credentials or message bodies.
        logger.error("Notification event receiver failed")


notification_event = NotificationSignal()


class NotificationEventKind:
    """Public event-name vocabulary."""

    CREATED = "notification.created"
    UPDATED = "notification.updated"
    SENT = "notification.sent"
    SEEN = "notification.seen"
    UNSEEN = "notification.unseen"
    CLEARED = "notification.cleared"
    HARD_DELETED = "notification.hard_deleted"


@dataclass(frozen=True)
# Immutable public event schema; each field is part of the payload contract.
# pylint: disable-next=too-many-instance-attributes
class NotificationEvent:
    """Minimal safe metadata for one lifecycle action.

    ``affected_count`` means eligible candidate rows for a bulk operation; for conflict-
    tolerant bulk inserts it is not an exact new-row count under concurrent requests.
    Bulk events intentionally omit individual IDs.

    """

    kind: str
    database: str
    notification_id: int | None = None
    user_id: int | None = None
    affected_count: int = 1
    batch: bool = False
    is_sent: bool | None = None
    fields: tuple[str, ...] = ()


def publish_notification_event(event: NotificationEvent) -> None:
    """Publish via post-commit signal or opt-in transactional outbox.

    Signal receivers use ``send_robust`` so a broken receiver does not turn a committed
    DB operation into an API error. Failures are logged generically, without serializing
    notification content, user data, or exception messages.

    """
    delivery_mode = getattr(
        settings, "DJANGO_NOTIFICATION_API_EVENT_DELIVERY", "signal"
    )
    if delivery_mode == "outbox":
        from django_notification.outbox import enqueue_event

        enqueue_event(event)
        return
    if delivery_mode != "signal":
        raise ValueError("Unsupported notification event delivery mode")

    def dispatch():
        from django_notification.models.notification import Notification

        notification_event.send_robust(sender=Notification, event=event)

    transaction.on_commit(dispatch, using=event.database, robust=True)
