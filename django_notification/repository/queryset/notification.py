"""Composable query operations for notification targeting and user state."""

import warnings
from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Exists, ManyToManyField, Model, OuterRef, Q, QuerySet
from django.utils import timezone

from django_notification.constants.qs_types import (
    ActionObject,
    Actor,
    Data,
    Description,
    Groups,
    Link,
    OptConditions,
    Recipient,
    Recipients,
    Target,
)
from django_notification.models.deleted_notification import DeletedNotification
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.notification_preference import NotificationPreference
from django_notification.models.notification_recipient import NotificationRecipient
from django_notification.models.notification_seen import NotificationSeen
from django_notification.repository.legacy_projection import (
    legacy_notification_projection,
)
from django_notification.utils.user_model import UserModel

_GROUPS_FIELD_NAME = "groups"

if TYPE_CHECKING:
    # Explicit re-export preserves this annotation import through unused-import checks.
    # pylint: disable-next=useless-import-alias
    from django_notification.models.notification import Notification as Notification


# pylint: disable=too-many-arguments
# Retain legacy selectors/mutation shims alongside the composable public API.
# pylint: disable-next=too-many-public-methods
class NotificationQuerySet(QuerySet["Notification"]):
    """Build unique notification selections without multi-valued joins.

    Chainable selectors return model instances. Deprecated public selectors still
    delegate to a separate legacy projection adapter for compatibility.

    """

    def with_related(self) -> "NotificationQuerySet":
        """Prefetch associations needed by the full-detail serializer."""
        return self.prefetch_related(
            "recipient", "group", "group__permissions", "seen_by"
        )

    @staticmethod
    def _valid_user(user: UserModel | None) -> bool:
        """Reject anonymous, unsaved and inactive users for personal feeds."""
        return bool(
            user is not None
            and getattr(user, "pk", None) is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", True)
        )

    @staticmethod
    def _identities(items):
        """Normalize one model or a collection to IDs without evaluating a QuerySet."""
        if isinstance(items, Model):
            return [items.pk]
        if isinstance(items, QuerySet):
            return items.values_list("pk", flat=True)
        return [item.pk if isinstance(item, Model) else item for item in items]

    def targeted_to(
        self, recipients: Recipients = None, groups: Groups = None
    ) -> "NotificationQuerySet":
        """Match direct recipients OR targeted groups without duplicate rows.

        ``None`` means no constraint for that dimension. Explicit empty inputs
        do not widen the queryset; if both are empty, the result is empty.
        If both are None, this acts as an unfiltered selection for admin code.

        """
        matches = []
        if recipients is not None:
            recipients_qs = NotificationRecipient.objects.using(self.db).filter(
                notification_id=OuterRef("pk"),
                recipient_id__in=self._identities(recipients),
            )
            matches.append(Exists(recipients_qs))
        if groups is not None:
            groups_qs = self.model.group.through.objects.using(self.db).filter(
                notification_id=OuterRef("pk"),
                group_id__in=self._identities(groups),
            )
            matches.append(Exists(groups_qs))

        if not matches:
            return self.all()
        predicate = Q(matches[0])
        for other in matches[1:]:
            predicate |= Q(other)
        return self.filter(predicate)

    def visible_to(self, user: UserModel) -> "NotificationQuerySet":
        """Limit records to a direct recipient or member of a targeted group.

        Dynamic groups use current membership; snapshot groups are resolved
        through persisted direct-recipient rows. Staff never bypass this rule.
        Users without ``groups`` can still receive direct notifications.

        """
        if not self._valid_user(user):
            return self.none()

        recipient = NotificationRecipient.objects.using(self.db).filter(
            notification_id=OuterRef("pk"), recipient_id=user.pk
        )
        visibility = Q(Exists(recipient))
        membership = getattr(user, _GROUPS_FIELD_NAME, None)
        groups_field = None
        if membership is not None:
            try:
                groups_field = user._meta.get_field(_GROUPS_FIELD_NAME)
            except FieldDoesNotExist:
                pass
        if (
            membership is not None
            and isinstance(groups_field, ManyToManyField)
            and groups_field.remote_field.model is Group
        ):
            targeted_group = self.model.group.through.objects.using(self.db).filter(
                notification_id=OuterRef("pk"),
                group_id__in=membership.values_list("pk", flat=True).using(self.db),
            )
            # Snapshot recipients are persisted as direct recipient rows.
            # Group membership must never widen a frozen notification.
            dynamic_groups = Q(group_audience_mode=GroupAudienceMode.DYNAMIC)
            visibility |= dynamic_groups & Q(Exists(targeted_group))
        # User preferences control only personal visibility, never the
        # recipient/group records. Mandatory categories bypass legacy opt-outs.
        disabled = NotificationPreference.objects.using(self.db).filter(
            user_id=user.pk,
            category_id=OuterRef("category_id"),
            category__is_mandatory=False,
            enabled=False,
        )
        return self.filter(visibility).filter(~Exists(disabled))

    def in_category(self, slug: str) -> "NotificationQuerySet":
        """Select one managed category; does not affect recipient visibility."""
        return self.filter(category_id=slug)

    def with_priority(self, priority: str) -> "NotificationQuerySet":
        """Select one independent notification priority level."""
        return self.filter(priority=priority)

    def active_at(self, when=None) -> "NotificationQuerySet":
        """Notifications whose expiration has not yet elapsed.

        A null expiry means no expiration. At the exact expiry instant, the
        record is expired. Supplying ``when`` lets applications use a stable
        reference time throughout multi-query reporting.

        """
        when = timezone.now() if when is None else when
        return self.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=when))

    def expired_at(self, when=None) -> "NotificationQuerySet":
        """Select expired records for administrator-led retention workflows."""
        when = timezone.now() if when is None else when
        return self.filter(expires_at__lte=when)

    def sent_only(self) -> "NotificationQuerySet":
        """Return sent notifications as model instances."""
        return self.filter(is_sent=True)

    def unsent_only(self) -> "NotificationQuerySet":
        """Return unsent notifications as model instances."""
        return self.filter(is_sent=False)

    def seen_by(self, user: UserModel) -> "NotificationQuerySet":
        """Filter by the specified user's independent read state."""
        if not self._valid_user(user):
            return self.none()
        rows = NotificationSeen.objects.using(self.db).filter(
            notification_id=OuterRef("pk"), user_id=user.pk
        )
        return self.filter(Exists(rows))

    def unseen_by(self, user: UserModel) -> "NotificationQuerySet":
        """Exclude notifications marked as seen by this user."""
        if not self._valid_user(user):
            return self.none()
        rows = NotificationSeen.objects.using(self.db).filter(
            notification_id=OuterRef("pk"), user_id=user.pk
        )
        return self.filter(~Exists(rows))

    def not_deleted_by(self, user: UserModel) -> "NotificationQuerySet":
        """Exclude only this user's soft-deleted notifications."""
        if not self._valid_user(user):
            return self.none()
        rows = DeletedNotification.objects.using(self.db).filter(
            notification_id=OuterRef("pk"), user_id=user.pk
        )
        return self.filter(~Exists(rows))

    def deleted_by(self, user: UserModel) -> "NotificationQuerySet":
        """Select notifications that this user soft-deleted."""
        if not self._valid_user(user):
            return self.none()
        rows = DeletedNotification.objects.using(self.db).filter(
            notification_id=OuterRef("pk"), user_id=user.pk
        )
        return self.filter(Exists(rows))

    def all_notifications(
        self,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
    ) -> QuerySet:
        """Legacy selector: all statuses, targeting by recipient OR group."""
        return legacy_notification_projection(
            self.targeted_to(recipients, groups), display_detail
        )

    def _legacy_status(
        self,
        is_sent: bool,
        recipients: Recipients,
        exclude_deleted_by: Recipient,
        groups: Groups,
        display_detail: bool,
        conditions: OptConditions,
    ) -> QuerySet:
        """Apply compatibility filters using one consistent target rule."""
        queryset: NotificationQuerySet = self.filter(is_sent=is_sent)
        if exclude_deleted_by is not None:
            # Only the user's own visible records can participate. Passing an
            # unrelated explicit group must not override this access boundary.
            queryset = queryset.visible_to(exclude_deleted_by)
            queryset = queryset.active_at()
            queryset = queryset.not_deleted_by(exclude_deleted_by)
        queryset = queryset.targeted_to(recipients, groups)
        if conditions is not None:
            queryset = queryset.filter(conditions)
        return legacy_notification_projection(queryset, display_detail)

    def sent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: OptConditions = None,
    ) -> QuerySet:
        """Legacy sent selector; prefer ``sent_only()`` for composition."""
        return self._legacy_status(
            True, recipients, exclude_deleted_by, groups, display_detail, conditions
        )

    def unsent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: OptConditions = None,
    ) -> QuerySet:
        """Legacy unsent selector; prefer ``unsent_only()`` for composition."""
        return self._legacy_status(
            False, recipients, exclude_deleted_by, groups, display_detail, conditions
        )

    def seen(
        self,
        seen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: OptConditions = None,
    ) -> QuerySet:
        """Legacy seen feed, including direct and group recipients by default."""
        queryset = (
            self.visible_to(seen_by)
            .active_at()
            .sent_only()
            .seen_by(seen_by)
            .not_deleted_by(seen_by)
            .targeted_to(recipients, groups)
        )
        if conditions is not None:
            queryset = queryset.filter(conditions)
        return legacy_notification_projection(queryset, display_detail)

    def unseen(
        self,
        unseen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: OptConditions = None,
    ) -> QuerySet:
        """Legacy unseen feed, including direct and group recipients by default."""
        queryset = (
            self.visible_to(unseen_by)
            .active_at()
            .sent_only()
            .unseen_by(unseen_by)
            .not_deleted_by(unseen_by)
            .targeted_to(recipients, groups)
        )
        if conditions is not None:
            queryset = queryset.filter(conditions)
        return legacy_notification_projection(queryset, display_detail)

    def deleted(self, deleted_by: Recipient = None) -> "NotificationQuerySet":
        """Select deleted records, optionally scoped to a user's deletion state."""
        if deleted_by is not None:
            return self.deleted_by(deleted_by).with_related()
        deleted_rows = DeletedNotification.objects.using(self.db).filter(
            notification_id=OuterRef("pk")
        )
        return self.filter(Exists(deleted_rows)).with_related()

    # Compatibility layer for applications using queryset mutation methods.
    # The manager routes directly to the service; these shims are deprecated.
    def _legacy_lifecycle(self):
        """Delegate a legacy queryset mutation to the lifecycle service."""
        from django_notification.services.notification import (
            NotificationLifecycleService,
        )

        warnings.warn(
            "Calling mutation methods on NotificationQuerySet is deprecated; "
            "use Notification.objects or NotificationLifecycleService instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return NotificationLifecycleService(self)

    # Deprecated facade retains the same named creation parameters.
    # pylint: disable-next=too-many-locals
    def create_notification(
        self,
        verb: str,
        actor: Actor,
        description: Description = None,
        status: str = "INFO",
        public: bool = True,
        target: Target = None,
        action_object: ActionObject = None,
        link: Link = None,
        is_sent: bool = False,
        data: Data = None,
        group_audience_mode: str = GroupAudienceMode.DYNAMIC,
        *,
        recipients: Recipients = None,
        groups: Groups = None,
        idempotency_key: str | None = None,
        deduplication_key: str | None = None,
        deduplication_window=None,
        expires_at=None,
        category: str = "general",
        priority: str = "NORMAL",
    ):
        """Deprecated queryset entry point for notification creation."""
        return self._legacy_lifecycle().create_notification(
            verb,
            actor,
            description,
            status=status,
            public=public,
            target=target,
            action_object=action_object,
            link=link,
            is_sent=is_sent,
            data=data,
            group_audience_mode=group_audience_mode,
            recipients=recipients,
            groups=groups,
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
        data: Data = None,
    ):
        """Deprecated queryset entry point for selective updates."""
        return self._legacy_lifecycle().update_notification(
            notification_id, is_sent=is_sent, public=public, data=data
        )

    def delete_notification(
        self,
        notification_id: int,
        recipient: Recipient = None,
        soft_delete: bool = True,
    ) -> None:
        """Deprecated queryset entry point for soft/hard delete."""
        self._legacy_lifecycle().delete_notification(
            notification_id, recipient=recipient, soft_delete=soft_delete
        )

    def mark_all_as_sent(
        self, recipients: Recipients = None, groups: Groups = None
    ) -> int:
        """Deprecated queryset entry point for bulk sent-state updates."""
        return self._legacy_lifecycle().mark_all_as_sent(recipients, groups)

    def mark_all_as_seen(self, user: UserModel) -> int:
        """Deprecated queryset entry point for bulk read-state updates."""
        return self._legacy_lifecycle().mark_all_as_seen(user)

    def clear_all(self, user: UserModel) -> None:
        """Deprecated queryset entry point for bulk soft deletion."""
        self._legacy_lifecycle().clear_all(user)
