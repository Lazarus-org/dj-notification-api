"""Public notification manager combining query and lifecycle APIs."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from django.db.models import Manager

from django_notification.constants.qs_types import (
    ActionObject,
    Actor,
    Data,
    Description,
    Groups,
    Link,
    Recipient,
    Recipients,
    Target,
)
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.repository.queryset.notification import NotificationQuerySet
from django_notification.services.notification import NotificationLifecycleService
from django_notification.utils.user_model import UserModel

if TYPE_CHECKING:
    from django_notification.models.notification import Notification


NotificationQueryManager = Manager.from_queryset(NotificationQuerySet)


# pylint: disable=too-many-arguments
class NotificationDataAccessLayer(NotificationQueryManager):
    """Expose chainable selections plus transactional notification mutations.

    ``Manager.from_queryset`` publishes the queryset's read-only filters. Creation,
    updates and per-user state transitions live in the lifecycle service instead of on
    the queryset. Existing manager calls remain usable.

    """

    def _lifecycle(self) -> NotificationLifecycleService:
        """Bind mutations to this manager's database and base queryset."""
        return NotificationLifecycleService(
            cast(NotificationQuerySet, self.get_queryset())
        )

    # This compatibility facade forwards the established named creation arguments.
    # pylint: disable-next=too-many-locals
    def create_notification(
        self,
        verb: str,
        actor: Actor,
        description: Description | None = None,
        recipients: Recipients | None = None,
        groups: Groups | None = None,
        status: str = "INFO",
        public: bool = True,
        target: Target | None = None,
        action_object: ActionObject | None = None,
        link: Link | None = None,
        is_sent: bool = False,
        data: Data | None = None,
        group_audience_mode: str = GroupAudienceMode.DYNAMIC,
        *,
        idempotency_key: str | None = None,
        deduplication_key: str | None = None,
        deduplication_window: timedelta | None = None,
        expires_at: datetime | None = None,
        category: str = "general",
        priority: str = NotificationPriority.NORMAL,
    ) -> "Notification":
        """Create, or reuse a notification via an optional trusted event key."""
        return self._lifecycle().create_notification(
            verb=verb,
            actor=actor,
            description=description,
            recipients=recipients,
            groups=groups,
            status=status,
            public=public,
            target=target,
            action_object=action_object,
            link=link,
            is_sent=is_sent,
            data=data,
            group_audience_mode=group_audience_mode,
            idempotency_key=idempotency_key,
            deduplication_key=deduplication_key,
            deduplication_window=deduplication_window,
            expires_at=expires_at,
            category=category,
            priority=priority,
        )

    def update_notification(
        self,
        notification_id: int,
        is_sent: bool | None = None,
        public: bool | None = None,
        data: Data | None = None,
    ) -> "Notification":
        """Update only explicitly supplied fields on an existing notification."""
        return self._lifecycle().update_notification(
            notification_id, is_sent=is_sent, public=public, data=data
        )

    def delete_notification(
        self,
        notification_id: int,
        recipient: Recipient | None = None,
        soft_delete: bool = True,
    ) -> None:
        """Soft-delete a recipient's notification or explicitly hard-delete it."""
        self._lifecycle().delete_notification(notification_id, recipient, soft_delete)

    def mark_all_as_sent(
        self, recipients: Recipients | None = None, groups: Groups | None = None
    ) -> int:
        """Mark unsent matching notifications as sent in one database update."""
        return self._lifecycle().mark_all_as_sent(recipients, groups)

    def set_seen(
        self, user: UserModel, notification_id: int | str | None, seen: bool
    ) -> bool:
        """Set one visible notification's per-user read state."""
        return self._lifecycle().set_seen(user, notification_id, seen)

    def set_many_seen(self, user: UserModel, ids, seen: bool) -> int:
        """Update an explicit list of visible notifications atomically."""
        return self._lifecycle().set_many_seen(user, ids, seen)

    def clear_selected(self, user: UserModel, ids) -> int:
        """Soft-delete an explicit list of the user's seen activities."""
        return self._lifecycle().clear_selected(user, ids)

    def mark_all_as_seen(self, user: UserModel) -> int:
        """Mark a user's unseen, visible notifications as seen in bounded batches."""
        return self._lifecycle().mark_all_as_seen(user)

    def clear_all(self, user: UserModel) -> None:
        """Soft-delete all of the user's seen activities in bounded batches."""
        self._lifecycle().clear_all(user)
