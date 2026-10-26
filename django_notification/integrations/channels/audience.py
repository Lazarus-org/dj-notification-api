"""Resolve eligible recipients without N+1 queries or multi-value join duplicates."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from django_notification.models import Notification
from django_notification.models.deleted_notification import DeletedNotification
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.notification_preference import NotificationPreference
from django_notification.models.notification_recipient import NotificationRecipient


def active_user(user_id, database):
    """Check that a persisted, active identity still exists on this database."""
    users = get_user_model()._default_manager.db_manager(database).all()
    query = users.filter(pk=user_id)
    if any(field.name == "is_active" for field in users.model._meta.fields):
        query = query.filter(is_active=True)
    user = query.first()
    if user is None or not getattr(user, "is_active", True):
        return None
    return user


def notification_visible(user_id, notification_id, database):
    """Recheck personal visibility *after* group delivery but before socket send."""
    user = active_user(user_id, database)
    if user is None:
        return False, False
    eligible = (
        Notification.objects.using(database)
        .visible_to(user)
        .active_at()
        .sent_only()
        .not_deleted_by(user)
    )
    return True, eligible.filter(pk=notification_id).exists()


# Bounded audience selection keeps independent eligibility subqueries explicit.
# pylint: disable-next=too-many-locals
def eligible_audience(notification_id, database):
    """Yield user PKs for one live, sent notification in bounded keyset batches.

    The audience includes direct targets (including snapshot recipients) and current
    members of dynamic Django auth groups. Neither staff status nor group permissions
    widen visibility. Disabled optional categories and individual soft deletion are
    excluded before dispatch.

    """
    notification = (
        Notification.objects.using(database)
        .active_at(timezone.now())
        .sent_only()
        .filter(pk=notification_id)
        .values("pk", "category_id", "group_audience_mode")
        .first()
    )
    if notification is None:
        return

    users = get_user_model()._default_manager.db_manager(database).all()
    if any(field.name == "is_active" for field in users.model._meta.fields):
        users = users.filter(is_active=True)
    direct = NotificationRecipient.objects.using(database).filter(
        notification_id=notification_id, recipient_id=OuterRef("pk")
    )
    audience = Q(Exists(direct))

    if notification["group_audience_mode"] == GroupAudienceMode.DYNAMIC:
        try:
            field = users.model._meta.get_field("groups")
        except FieldDoesNotExist:
            field = None
        if (
            field is not None
            and field.many_to_many
            and field.remote_field.model is Group
        ):
            group_ids = (
                Notification.group.through.objects.using(database)
                .filter(notification_id=notification_id)
                .values("group_id")
            )
            through = field.remote_field.through
            if through is None:
                raise ValueError("Group membership requires a through model")
            membership = through._default_manager.using(database).filter(
                **{
                    f"{field.m2m_field_name()}_id": OuterRef("pk"),
                    f"{field.m2m_reverse_field_name()}_id__in": group_ids,
                }
            )
            audience |= Q(Exists(membership))

    deleted = DeletedNotification.objects.using(database).filter(
        notification_id=notification_id, user_id=OuterRef("pk")
    )
    opted_out = NotificationPreference.objects.using(database).filter(
        user_id=OuterRef("pk"),
        category_id=notification["category_id"],
        category__is_mandatory=False,
        enabled=False,
    )
    users = users.filter(audience).filter(~Exists(deleted), ~Exists(opted_out))

    # The maximum PK fixes a finite scope if new users are created mid-fanout.
    ceiling = users.order_by("-pk").values_list("pk", flat=True).first()
    if ceiling is None:
        return
    last_pk = None
    while True:
        page = users.filter(pk__lte=ceiling)
        if last_pk is not None:
            page = page.filter(pk__gt=last_pk)
        ids = list(page.order_by("pk").values_list("pk", flat=True)[:500])
        if not ids:
            return
        yield from ids
        last_pk = ids[-1]
