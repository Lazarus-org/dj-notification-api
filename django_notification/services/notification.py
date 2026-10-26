"""Transactional notification lifecycle operations, separate from query building."""

import json
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from hashlib import sha256
from typing import cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import ManyToManyField, Model
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

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
from django_notification.events import (
    NotificationEvent,
    NotificationEventKind,
    publish_notification_event,
)
from django_notification.models.deleted_notification import DeletedNotification
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.models.notification_category import NotificationCategory
from django_notification.models.notification_creation_key import (
    CreationKeyKind,
    NotificationCreationKey,
)
from django_notification.models.notification_recipient import NotificationRecipient
from django_notification.models.notification_seen import NotificationSeen
from django_notification.repository.queryset.notification import NotificationQuerySet
from django_notification.utils.user_model import UserModel

_BATCH_SIZE = 500


class NotificationLifecycleService:
    """Perform state changes using the caller's queryset and database alias.

    The user's current direct-recipient/group visibility is rechecked for each selected
    batch. Per-user state tables have unique (notification, user) constraints; conflict-
    tolerant inserts allow concurrent repeated requests.

    """

    def __init__(self, queryset: NotificationQuerySet):
        self.queryset = queryset
        self.db = queryset.db

    # Named metadata fields mirror the immutable public event schema.
    # pylint: disable-next=too-many-arguments
    def _emit(
        self,
        kind,
        *,
        notification_id=None,
        user_id=None,
        affected_count=1,
        batch=False,
        is_sent=None,
        fields=(),
    ):
        """Register immutable metadata for post-commit signal delivery."""
        publish_notification_event(
            NotificationEvent(
                kind=kind,
                database=self.db,
                notification_id=notification_id,
                user_id=user_id,
                affected_count=affected_count,
                batch=batch,
                is_sent=is_sent,
                fields=tuple(fields),
            )
        )

    @staticmethod
    def _items(value):
        """Normalize a single model or iterable for M2M additions."""
        if value is None:
            return ()
        if isinstance(value, Model):
            return (value,)
        return value

    def _snapshot_group_recipients(self, notification):
        """Persist group members with bounded writes, retaining recipient overlap.

        Resolves membership inside the creation transaction. Once stored, group
        changes do not affect the frozen audience. A user model must define a
        ManyToManyField named ``groups`` targeting Django's Group model.

        """
        if not notification.group.exists():
            return
        user_model = get_user_model()
        try:
            groups_field = user_model._meta.get_field("groups")
        except FieldDoesNotExist as error:
            raise ValueError(
                "Snapshot groups require a user model with a groups M2M field"
            ) from error
        if (
            not isinstance(groups_field, ManyToManyField)
            or groups_field.remote_field.model is not Group
        ):
            raise ValueError("Snapshot groups require a groups M2M to auth.Group")

        group_ids = notification.group.values_list("pk", flat=True)
        member_ids = (
            user_model._default_manager.using(self.db)
            .filter(groups__pk__in=group_ids)
            .order_by("pk")
            .distinct()
            .values_list("pk", flat=True)
        )
        maximum_pk = member_ids.last()
        if maximum_pk is None:
            return
        last_pk = None
        while True:
            batch = member_ids.filter(pk__lte=maximum_pk)
            if last_pk is not None:
                batch = batch.filter(pk__gt=last_pk)
            ids = list(batch[:_BATCH_SIZE])
            if not ids:
                break
            NotificationRecipient.objects.using(self.db).bulk_create(
                [
                    NotificationRecipient(
                        notification_id=notification.pk, recipient_id=pk
                    )
                    for pk in ids
                ],
                batch_size=_BATCH_SIZE,
                ignore_conflicts=True,
            )
            last_pk = ids[-1]

    @staticmethod
    def _validate_creation_keys(
        idempotency_key, deduplication_key, deduplication_window
    ):
        """Reject ambiguous modes and unsafe/unbounded external key values."""
        for key in (idempotency_key, deduplication_key):
            if key is None:
                continue
            if (
                not isinstance(key, str)
                or not key
                or key != key.strip()
                or len(key) > 200
            ):
                raise ValueError("Creation keys must be 1–200 nonblank characters")
        if idempotency_key is not None and deduplication_key is not None:
            raise ValueError("Use either idempotency or deduplication, not both")
        if deduplication_key is None:
            if deduplication_window is not None:
                raise ValueError("A deduplication key is required for its window")
        elif not isinstance(
            deduplication_window, timedelta
        ) or deduplication_window <= timedelta(0):
            raise ValueError("A positive timedelta deduplication_window is required")

    @staticmethod
    def _model_identity(obj):
        """Canonical persisted object identity for retry fingerprinting."""
        if obj is None:
            return None
        if not isinstance(obj, Model) or obj.pk is None:
            raise ValueError("Related objects must be persisted Django models")
        return [
            cast(type[Model], obj._meta.concrete_model)._meta.label_lower,
            str(obj.pk),
        ]

    @classmethod
    def _target_ids(cls, values):
        """Normalize collections independent of order and duplicates."""
        result = set()
        for value in values:
            if isinstance(value, Model):
                if value.pk is None:
                    raise ValueError("Recipients and groups must be saved")
                result.add(str(value.pk))
            elif isinstance(value, (int, str)) and not isinstance(value, bool):
                result.add(str(value))
            else:
                raise ValueError("Recipients and groups must be saved models or IDs")
        return sorted(result)

    @classmethod
    def _creation_fingerprint(cls, payload, recipients, groups):
        """Hash logical creation arguments, not mutable notification state.

        Snapshot membership is deliberately excluded: identical retries after
        membership changes must return the original frozen audience.

        """
        identity = {
            "verb": payload["verb"],
            "actor": cls._model_identity(payload["actor"]),
            "description": payload["description"],
            "recipient_ids": cls._target_ids(recipients),
            "group_ids": cls._target_ids(groups),
            "status": payload["status"],
            "public": payload["public"],
            "target": cls._model_identity(payload["target"]),
            "action_object": cls._model_identity(payload["action_object"]),
            "link": payload["link"],
            "is_sent": payload["is_sent"],
            "data": payload["data"],
            "group_audience_mode": payload["group_audience_mode"],
            "category_id": payload["category_id"],
            "priority": payload["priority"],
            "expires_at": payload["expires_at"],
        }
        encoded = json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
            cls=DjangoJSONEncoder,
            allow_nan=False,
        )
        return sha256(encoded.encode("utf-8")).hexdigest()

    @classmethod
    def _deduplication_scope(cls, payload, recipients, groups):
        """Bound coalescing to one actor, object, and intended audience."""
        identity = {
            "actor": cls._model_identity(payload["actor"]),
            "target": cls._model_identity(payload["target"]),
            "action_object": cls._model_identity(payload["action_object"]),
            "recipient_ids": cls._target_ids(recipients),
            "group_ids": cls._target_ids(groups),
            "group_audience_mode": payload["group_audience_mode"],
            "category_id": payload["category_id"],
            "priority": payload["priority"],
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _insert_notification(self, payload, recipients, groups):
        """Insert notification, relations, and any snapshot in one transaction."""
        notification = self.queryset.create(**payload)
        if recipients is not None:
            notification.recipient.add(*self._items(recipients))
        if groups is not None:
            notification.group.add(*self._items(groups))
        if payload["group_audience_mode"] == GroupAudienceMode.SNAPSHOT:
            self._snapshot_group_recipients(notification)
        # Queue after all M2M assignments; retries that reuse a creation key
        # return the original row without scheduling another created event.
        self._emit(
            NotificationEventKind.CREATED,
            notification_id=notification.pk,
            is_sent=notification.is_sent,
        )
        return notification

    # Preserve the established creation API and explicit validation of its inputs.
    # pylint: disable-next=too-many-arguments,too-many-locals,too-many-branches
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
    ):
        """Create once per event key, or coalesce repeats within a time window.

        Keys are for trusted application callers. All key claims, recipient writes, and
        group snapshot writes share one transaction and DB alias.

        """
        if group_audience_mode not in GroupAudienceMode.values:
            raise ValueError("Unsupported group audience mode")
        if priority not in NotificationPriority.values:
            raise ValueError("Unsupported notification priority")
        category_slug = (
            category.pk if isinstance(category, NotificationCategory) else category
        )
        if not isinstance(category_slug, str) or not category_slug:
            raise ValueError("category must be an existing active category slug")
        if (
            not NotificationCategory.objects.using(self.db)
            .filter(pk=category_slug, is_active=True)
            .exists()
        ):
            raise ValueError("category must be an existing active category slug")
        if expires_at is not None:
            if not isinstance(expires_at, datetime):
                raise ValueError("expires_at must be a timezone-aware datetime or None")
            if settings.USE_TZ and timezone.is_naive(expires_at):
                raise ValueError("expires_at must be timezone-aware when USE_TZ=True")
            if not settings.USE_TZ and timezone.is_aware(expires_at):
                raise ValueError("expires_at must be naive when USE_TZ=False")
            if settings.USE_TZ:
                # Identical expiry instants must share an idempotency fingerprint
                # regardless of the caller's timezone/UTC offset.
                expires_at = expires_at.astimezone(datetime_timezone.utc)
        self._validate_creation_keys(
            idempotency_key, deduplication_key, deduplication_window
        )
        payload = {
            "verb": verb,
            "actor": actor,
            "description": description,
            "status": status,
            "public": public,
            "target": target,
            "action_object": action_object,
            "link": link,
            "is_sent": is_sent,
            "data": data,
            "group_audience_mode": group_audience_mode,
            "category_id": category_slug,
            "priority": priority,
            "expires_at": expires_at,
        }
        if idempotency_key is None and deduplication_key is None:
            with transaction.atomic(using=self.db):
                return self._insert_notification(payload, recipients, groups)

        # For keyed creation, materialize generators once so fingerprinting
        # and M2M assignment use exactly the same intended audience.
        recipients = tuple(self._items(recipients))
        groups = tuple(self._items(groups))
        fingerprint = (
            self._creation_fingerprint(payload, recipients, groups)
            if idempotency_key is not None
            else self._deduplication_scope(payload, recipients, groups)
        )
        kind = (
            CreationKeyKind.IDEMPOTENCY
            if idempotency_key is not None
            else CreationKeyKind.DEDUPLICATION
        )
        key = idempotency_key if idempotency_key is not None else deduplication_key
        with transaction.atomic(using=self.db):
            # The unique(kind, key) constraint serializes concurrent creators.
            # Django get_or_create handles an insert race using a savepoint.
            claims = NotificationCreationKey.objects.using(self.db)
            claim, _ = claims.get_or_create(kind=kind, key=key)
            claim = claims.select_for_update().get(pk=claim.pk)
            existing_notification = claim.notification
            if existing_notification is not None:
                if kind == CreationKeyKind.IDEMPOTENCY:
                    if claim.request_fingerprint != fingerprint:
                        raise ValueError(
                            "An idempotency key was reused for a different event"
                        )
                    return existing_notification
                now = timezone.now()
                if claim.expires_at is not None and claim.expires_at > now:
                    if claim.request_fingerprint != fingerprint:
                        raise ValueError(
                            "A deduplication key was reused for a different audience"
                        )
                    # An already-expired notification must not suppress a new
                    # event, even while the deduplication window is open.
                    notification_expiry = existing_notification.expires_at
                    if notification_expiry is None or notification_expiry > now:
                        return existing_notification
            notification = self._insert_notification(payload, recipients, groups)
            claim.notification = notification
            claim.request_fingerprint = fingerprint
            claim.expires_at = (
                timezone.now() + deduplication_window
                if deduplication_window is not None
                else None
            )
            claim.save(
                using=self.db,
                update_fields=["notification", "request_fingerprint", "expires_at"],
            )
            return notification

    def update_notification(
        self,
        notification_id: int,
        is_sent: bool | None = None,
        public: bool | None = None,
        data: Data | None = None,
    ):
        """Update changed fields and emit after commit, never for no-op writes."""
        with transaction.atomic(using=self.db):
            notification = get_object_or_404(
                self.queryset.select_for_update(), pk=notification_id
            )
            was_sent = notification.is_sent
            fields = []
            for field, value in (
                ("is_sent", is_sent),
                ("public", public),
                ("data", data),
            ):
                if value is not None and getattr(notification, field) != value:
                    setattr(notification, field, value)
                    fields.append(field)
            if fields:
                notification.save(using=self.db, update_fields=fields)
                self._emit(
                    NotificationEventKind.UPDATED,
                    notification_id=notification.pk,
                    is_sent=notification.is_sent,
                    fields=fields,
                )
                if not was_sent and notification.is_sent:
                    self._emit(
                        NotificationEventKind.SENT,
                        notification_id=notification.pk,
                        is_sent=True,
                    )
            return notification

    def mark_all_as_sent(
        self, recipients: Recipients = None, groups: Groups = None
    ) -> int:
        """Send a finite selection and publish durable intent for each row."""
        with transaction.atomic(using=self.db):
            candidates = (
                self.queryset.unsent_only().active_at().targeted_to(recipients, groups)
            )
            count = 0
            for ids in self._batch_ids(candidates):
                # Recheck unsent state under row locks so concurrent service
                # calls cannot emit a second transition for the same row.
                changed_ids = list(
                    candidates.filter(pk__in=ids)
                    .select_for_update()
                    .order_by("pk")
                    .values_list("pk", flat=True)
                )
                candidates.filter(pk__in=changed_ids).update(is_sent=True)
                for pk in changed_ids:
                    self._emit(
                        NotificationEventKind.SENT,
                        notification_id=pk,
                        is_sent=True,
                    )
                count += len(changed_ids)
            if count:
                self._emit(
                    NotificationEventKind.SENT,
                    affected_count=count,
                    batch=True,
                    is_sent=True,
                )
            return count

    def _batch_ids(self, queryset: NotificationQuerySet):
        """Yield finite ascending keyset batches; never materialize the full feed."""
        # Freeze the upper key at operation start so new incoming events cannot
        # extend an in-progress bulk transaction indefinitely.
        max_pk = queryset.order_by("-pk").values_list("pk", flat=True).first()
        if max_pk is None:
            return
        last_pk = None
        while True:
            batch = queryset.filter(pk__lte=max_pk)
            if last_pk is not None:
                batch = batch.filter(pk__gt=last_pk)
            ids = list(batch.order_by("pk").values_list("pk", flat=True)[:_BATCH_SIZE])
            if not ids:
                return
            last_pk = ids[-1]
            yield ids

    def _personal_records(self, user: UserModel) -> NotificationQuerySet:
        """Only sent, undeleted notifications visible to an active user."""
        if not self.queryset._valid_user(user):
            return self.queryset.none()
        return (
            self.queryset.visible_to(user).active_at().sent_only().not_deleted_by(user)
        )

    def set_seen(
        self, user: UserModel, notification_id: int | str | None, seen: bool
    ) -> bool:
        """Idempotently change one user's state; return whether it changed."""
        if notification_id is None:
            raise Http404
        try:
            notification_id = int(notification_id)
        except (ValueError, TypeError):
            raise Http404 from None
        if notification_id < 1:
            raise Http404
        with transaction.atomic(using=self.db):
            notification = get_object_or_404(
                self._personal_records(user), pk=notification_id
            )
            rows = NotificationSeen.objects.using(self.db)
            if seen:
                _, created = rows.get_or_create(
                    user_id=user.pk, notification_id=notification.pk
                )
                if created:
                    self._emit(
                        NotificationEventKind.SEEN,
                        notification_id=notification.pk,
                        user_id=user.pk,
                    )
                return created
            deleted, _ = rows.filter(
                user_id=user.pk, notification_id=notification.pk
            ).delete()
            if deleted:
                self._emit(
                    NotificationEventKind.UNSEEN,
                    notification_id=notification.pk,
                    user_id=user.pk,
                )
            return bool(deleted)

    def set_many_seen(self, user: UserModel, ids, seen: bool) -> int:
        """Atomically apply a read-state action to an explicit bounded ID list.

        Reject the entire request with 404 if any ID is not visible. The count is the
        number of unique eligible IDs, not newly changed rows.

        """
        ids = list(dict.fromkeys(ids))
        if not ids or len(ids) > _BATCH_SIZE:
            raise ValueError("ids must contain between 1 and 500 items")
        with transaction.atomic(using=self.db):
            eligible = list(
                self._personal_records(user)
                .filter(pk__in=ids)
                .values_list("pk", flat=True)
            )
            if len(eligible) != len(ids):
                raise Http404
            rows = NotificationSeen.objects.using(self.db)
            existing = set(
                rows.filter(notification_id__in=eligible, user_id=user.pk).values_list(
                    "notification_id", flat=True
                )
            )
            if seen:
                changed_ids = [pk for pk in eligible if pk not in existing]
                if changed_ids:
                    rows.bulk_create(
                        [
                            NotificationSeen(notification_id=pk, user_id=user.pk)
                            for pk in changed_ids
                        ],
                        batch_size=_BATCH_SIZE,
                        ignore_conflicts=True,
                    )
            else:
                changed_ids = [pk for pk in eligible if pk in existing]
                if changed_ids:
                    rows.filter(
                        notification_id__in=changed_ids, user_id=user.pk
                    ).delete()
            if changed_ids:
                self._emit(
                    (
                        NotificationEventKind.SEEN
                        if seen
                        else NotificationEventKind.UNSEEN
                    ),
                    user_id=user.pk,
                    affected_count=len(changed_ids),
                    batch=True,
                )
        return len(eligible)

    def clear_selected(self, user: UserModel, ids) -> int:
        """Soft-delete selected seen activities, all-or-nothing."""
        ids = list(dict.fromkeys(ids))
        if not ids or len(ids) > _BATCH_SIZE:
            raise ValueError("ids must contain between 1 and 500 items")
        with transaction.atomic(using=self.db):
            eligible = list(
                self._personal_records(user)
                .seen_by(user)
                .filter(pk__in=ids)
                .values_list("pk", flat=True)
            )
            if len(eligible) != len(ids):
                raise Http404
            DeletedNotification.objects.using(self.db).bulk_create(
                [
                    DeletedNotification(notification_id=pk, user_id=user.pk)
                    for pk in eligible
                ],
                batch_size=_BATCH_SIZE,
                ignore_conflicts=True,
            )
            if eligible:
                self._emit(
                    NotificationEventKind.CLEARED,
                    user_id=user.pk,
                    affected_count=len(eligible),
                    batch=True,
                )
        return len(eligible)

    def mark_all_as_seen(self, user: UserModel) -> int:
        """Mark only visible, sent, undeleted, unseen notifications.

        The returned number is the count of eligible candidate IDs processed. Under
        concurrent requests, more than one caller may process the same IDs; the unique
        DB constraint guarantees that only one row is saved.

        """
        if not self.queryset._valid_user(user):
            return 0
        queryset = (
            self.queryset.visible_to(user)
            .active_at()
            .sent_only()
            .unseen_by(user)
            .not_deleted_by(user)
        )
        count = 0
        with transaction.atomic(using=self.db):
            for ids in self._batch_ids(queryset):
                NotificationSeen.objects.using(self.db).bulk_create(
                    [
                        NotificationSeen(notification_id=pk, user_id=user.pk)
                        for pk in ids
                    ],
                    batch_size=_BATCH_SIZE,
                    ignore_conflicts=True,
                )
                count += len(ids)
            if count:
                self._emit(
                    NotificationEventKind.SEEN,
                    user_id=user.pk,
                    affected_count=count,
                    batch=True,
                )
        return count

    def clear_all(self, user: UserModel) -> None:
        """Soft-delete only visible, sent, seen and not-yet-cleared activities."""
        if not self.queryset._valid_user(user):
            return
        queryset = (
            self.queryset.visible_to(user)
            .active_at()
            .sent_only()
            .seen_by(user)
            .not_deleted_by(user)
        )
        with transaction.atomic(using=self.db):
            count = 0
            for ids in self._batch_ids(queryset):
                DeletedNotification.objects.using(self.db).bulk_create(
                    [
                        DeletedNotification(notification_id=pk, user_id=user.pk)
                        for pk in ids
                    ],
                    batch_size=_BATCH_SIZE,
                    ignore_conflicts=True,
                )
                count += len(ids)
            if count:
                self._emit(
                    NotificationEventKind.CLEARED,
                    user_id=user.pk,
                    affected_count=count,
                    batch=True,
                )

    def delete_notification(
        self,
        notification_id: int,
        recipient: Recipient | None = None,
        soft_delete: bool = True,
    ) -> None:
        """Soft-delete this recipient's sent notification, or hard-delete by ID.

        Hard deletion must only be called from an explicitly authorized admin context;
        the service deliberately does not infer authority from staff.

        """
        if soft_delete:
            if recipient is None or not self.queryset._valid_user(recipient):
                raise ValueError("a persisted active recipient is required")
            with transaction.atomic(using=self.db):
                instance = get_object_or_404(
                    self.queryset.visible_to(recipient)
                    .active_at()
                    .sent_only()
                    .not_deleted_by(recipient),
                    pk=notification_id,
                )
                _, created = DeletedNotification.objects.using(self.db).get_or_create(
                    notification_id=instance.pk, user_id=recipient.pk
                )
                if created:
                    self._emit(
                        NotificationEventKind.CLEARED,
                        notification_id=instance.pk,
                        user_id=recipient.pk,
                    )
            return

        with transaction.atomic(using=self.db):
            instance = get_object_or_404(self.queryset.sent_only(), pk=notification_id)
            deleted_id = instance.pk
            instance.delete(using=self.db)
            self._emit(
                NotificationEventKind.HARD_DELETED,
                notification_id=deleted_id,
            )
