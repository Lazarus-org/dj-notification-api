"""Regression tests for notification query composition and recipient isolation."""

import pytest
from django.contrib.auth.models import Group, User
from django.db.models import Q, QuerySet

from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationSeen,
)

pytestmark = pytest.mark.django_db


def test_explicit_empty_targets_do_not_widen_queries(
    notification: Notification, user: User, group: Group
) -> None:
    """Empty target inputs must never select unrelated notifications."""
    notification.recipient.add(user)
    notification.group.add(group)

    assert not Notification.objects.sent(recipients=[]).exists()
    assert not Notification.objects.sent(groups=[]).exists()
    assert not Notification.objects.unsent(recipients=[], groups=[]).exists()
    assert not Notification.objects.all_notifications(recipients=[]).exists()
    assert not Notification.objects.targeted_to(groups=[]).exists()

    # Only omitted filters, not explicitly empty filters, select all.
    assert Notification.objects.sent().count() == 1
    assert Notification.objects.targeted_to().count() == 1


def test_direct_or_group_matches_without_duplicates(
    notification: Notification, user: User, group: Group, qs_group: Group
) -> None:
    """Multiple direct/group matches never inflate count or pagination."""
    user.groups.add(group, qs_group)
    notification.recipient.add(user)
    notification.group.add(group, qs_group)

    queryset = Notification.objects.visible_to(user)
    assert queryset.count() == 1
    assert list(queryset.values_list("pk", flat=True)) == [notification.pk]

    targets = Notification.objects.targeted_to(
        recipients=[user], groups=[group, qs_group]
    )
    assert targets.count() == 1
    assert (
        Notification.objects.all_notifications(
            recipients=[user], groups=[group, qs_group]
        ).count()
        == 1
    )


def test_group_only_visibility_tracks_membership(
    notification: Notification, user: User, group: Group, admin_user: User
) -> None:
    """Group members see group-only records, but unrelated staff cannot."""
    notification.group.add(group)
    assert not Notification.objects.visible_to(user).exists()
    assert not Notification.objects.visible_to(admin_user).exists()

    user.groups.add(group)
    assert Notification.objects.visible_to(user).get() == notification
    assert Notification.objects.unseen(unseen_by=user).count() == 1

    user.groups.remove(group)
    assert not Notification.objects.visible_to(user).exists()
    assert not Notification.objects.unseen(unseen_by=user).exists()


def test_explicit_unauthorized_group_cannot_bypass_user_scope(
    notification: Notification, user: User, group: Group
) -> None:
    """A caller-supplied group never overrides personal-feed visibility."""
    notification.group.add(group)
    assert not Notification.objects.sent(groups=group, exclude_deleted_by=user).exists()
    assert not Notification.objects.seen(seen_by=user, groups=group).exists()
    assert not Notification.objects.unseen(unseen_by=user, groups=group).exists()


def test_recipient_or_group_not_recipient_and_group(
    notification: Notification, user: User, group: Group
) -> None:
    """Legacy all_notifications agrees with sent/unsent target semantics."""
    notification.recipient.add(user)
    assert (
        Notification.objects.all_notifications(recipients=user, groups=group).count()
        == 1
    )
    assert Notification.objects.sent(recipients=user, groups=group).count() == 1


def test_read_and_delete_state_belong_to_individual_users(
    notification: Notification, user: User, another_user: User, group: Group
) -> None:
    """One group recipient's mutations never hide other members' records."""
    user.groups.add(group)
    another_user.groups.add(group)
    notification.group.add(group)
    NotificationSeen.objects.create(notification=notification, user=user)
    DeletedNotification.objects.create(notification=notification, user=user)

    assert not Notification.objects.unseen(unseen_by=user).exists()
    assert not Notification.objects.seen(seen_by=user).exists()  # deleted
    assert Notification.objects.deleted_by(user).count() == 1
    assert Notification.objects.seen_by(user).count() == 1
    assert Notification.objects.unseen(unseen_by=another_user).count() == 1
    assert Notification.objects.not_deleted_by(another_user).count() == 1


def test_chainable_selectors_return_models_and_preserve_conditions(
    notification: Notification, user: User
) -> None:
    """Composable queryset calls keep model values and existing filters."""
    notification.recipient.add(user)
    queryset = (
        Notification.objects.filter(status=notification.status)
        .visible_to(user)
        .sent_only()
        .unseen_by(user)
        .not_deleted_by(user)
    )
    assert isinstance(queryset, QuerySet)
    assert queryset.get() == notification

    legacy = Notification.objects.sent(recipients=user, conditions=Q(verb="not this"))
    assert not legacy.exists()
    assert Notification.objects.sent(recipients=user).count() == 1
    assert (
        Notification.objects.sent(recipients=user, display_detail=True).get()
        == notification
    )


def test_inactive_and_unsaved_users_cannot_query_personal_feed(
    notification: Notification, user: User
) -> None:
    """No widening for invalid personal-feed principals."""
    notification.recipient.add(user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert not Notification.objects.visible_to(user).exists()
    assert not Notification.objects.unseen(unseen_by=user).exists()

    unsaved = User(username="not-persisted")
    assert not Notification.objects.visible_to(unsaved).exists()
    assert not Notification.objects.seen_by(unsaved).exists()
    assert not Notification.objects.not_deleted_by(unsaved).exists()
