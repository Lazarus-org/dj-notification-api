"""Group audience policies: dynamic targeting and opt-in membership snapshots."""

import pytest
from django.contrib.auth.models import Group, User
from django.http import Http404

from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationRecipient,
    NotificationSeen,
)
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.services import notification as lifecycle_module

pytestmark = pytest.mark.django_db


def test_business_group_ids_cannot_be_used_as_auth_group_membership(
    user, group, monkeypatch
):
    """Only auth.Group membership may authorize a targeted Django group."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import ManyToManyField

    user.groups.add(group)
    item = Notification.objects.create_notification(
        actor=user,
        verb="Auth group only",
        groups=[group],
        is_sent=True,
    )
    original = user._meta.get_field
    foreign_groups = ManyToManyField(ContentType)
    monkeypatch.setattr(
        user._meta,
        "get_field",
        lambda name: foreign_groups if name == "groups" else original(name),
    )
    assert not Notification.objects.visible_to(user).filter(pk=item.pk).exists()
    item.recipient.add(user)
    assert Notification.objects.visible_to(user).filter(pk=item.pk).exists()


def create(actor, **kwargs):
    """Create an already-sent notification through the public manager."""
    return Notification.objects.create_notification(
        verb="group event", actor=actor, is_sent=True, **kwargs
    )


def test_dynamic_is_default_and_follows_join_and_leave(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """Legacy group behavior remains dynamic without any snapshot rows."""
    user.groups.add(group)
    notification = create(user, groups=[group])
    assert notification.group_audience_mode == GroupAudienceMode.DYNAMIC
    assert notification.recipient.count() == 0
    assert Notification.objects.visible_to(user).filter(pk=notification.pk).exists()
    assert not Notification.objects.visible_to(another_user).exists()

    another_user.groups.add(group)
    assert (
        Notification.objects.visible_to(another_user)
        .filter(pk=notification.pk)
        .exists()
    )
    user.groups.remove(group)
    assert not Notification.objects.visible_to(user).filter(pk=notification.pk).exists()


def test_snapshot_preserves_creation_time_members(
    user: User,
    another_user: User,
    admin_user: User,
    group: Group,
) -> None:
    """Leaving a group does not revoke its past snapshot, joining grants none."""
    user.groups.add(group)
    notification = create(
        user,
        groups=group,
        group_audience_mode=GroupAudienceMode.SNAPSHOT,
    )
    assert list(notification.recipient.values_list("pk", flat=True)) == [user.pk]
    user.groups.remove(group)
    another_user.groups.add(group)

    assert Notification.objects.visible_to(user).filter(pk=notification.pk).exists()
    assert not Notification.objects.visible_to(another_user).exists()
    assert not Notification.objects.visible_to(admin_user).exists()
    assert (
        Notification.objects.unseen(unseen_by=user).filter(pk=notification.pk).exists()
    )
    assert not Notification.objects.unseen(unseen_by=another_user).exists()

    assert Notification.objects.set_seen(user, notification.pk, True)
    assert NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()
    assert Notification.objects.clear_selected(user, [notification.pk]) == 1
    assert DeletedNotification.objects.filter(
        notification=notification, user=user
    ).exists()
    with pytest.raises(Http404):
        Notification.objects.set_seen(another_user, notification.pk, True)


def test_snapshot_deduplicates_overlapping_direct_and_multiple_group_memberships(
    user: User,
    another_user: User,
    group: Group,
    qs_group: Group,
) -> None:
    """One recipient row per user regardless of how many targets match."""
    user.groups.add(group, qs_group)
    another_user.groups.add(qs_group)
    notification = create(
        user,
        recipients=[user],
        groups=Group.objects.filter(pk__in=[group.pk, qs_group.pk]),
        group_audience_mode="SNAPSHOT",
    )
    assert notification.group.count() == 2
    assert NotificationRecipient.objects.filter(notification=notification).count() == 2
    assert set(notification.recipient.values_list("pk", flat=True)) == {
        user.pk,
        another_user.pk,
    }
    assert Notification.objects.visible_to(user).filter(pk=notification.pk).count() == 1
    assert (
        Notification.objects.visible_to(another_user).filter(pk=notification.pk).count()
        == 1
    )
    user.groups.clear()
    another_user.groups.clear()
    assert Notification.objects.seen(seen_by=user).count() == 0
    assert Notification.objects.unseen(unseen_by=another_user).count() == 1


def test_snapshot_freezes_only_group_targets_and_keeps_explicit_direct_targets(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """An explicit recipient is authorized without ever belonging to the group."""
    user.groups.add(group)
    item = create(
        user,
        recipients=[another_user],
        groups=[group],
        group_audience_mode="SNAPSHOT",
    )
    user.groups.clear()
    assert set(item.recipient.values_list("pk", flat=True)) == {
        user.pk,
        another_user.pk,
    }
    assert Notification.objects.visible_to(another_user).filter(pk=item.pk).exists()


def test_invalid_mode_rejects_creation_before_writing(user: User, group: Group):
    """Unknown mode cannot silently fall back to a wider group policy."""
    before = Notification.objects.count()
    with pytest.raises(ValueError, match="Unsupported group audience mode"):
        create(user, groups=[group], group_audience_mode="incorrect")
    assert Notification.objects.count() == before


def test_snapshot_batching_is_bounded_and_retry_safe(
    monkeypatch,
    user: User,
    group: Group,
) -> None:
    """Snapshot recipient materialization uses chunks and a unique constraint."""
    monkeypatch.setattr(lifecycle_module, "_BATCH_SIZE", 2)
    members = [
        User.objects.create_user(username=f"snapshot-member-{index}")
        for index in range(5)
    ]
    for member in members:
        member.groups.add(group)
    notification = create(user, groups=[group], group_audience_mode="SNAPSHOT")
    assert notification.recipient.count() == len(members)
    notification.group.clear()
    for member in members:
        assert (
            Notification.objects.visible_to(member).filter(pk=notification.pk).exists()
        )
    # Re-materialization doesn't duplicate already persisted direct recipients.
    notification.group.add(group)
    lifecycle_module.NotificationLifecycleService(
        Notification.objects.get_queryset()
    )._snapshot_group_recipients(notification)
    assert notification.recipient.count() == len(members)


def test_snapshot_rolls_back_if_group_resolution_fails(
    monkeypatch,
    user: User,
    group: Group,
) -> None:
    """Failure while persisting frozen recipients leaves no orphan notification."""
    before = Notification.objects.count()

    def failure(*args, **kwargs):
        raise RuntimeError("snapshot write failed")

    monkeypatch.setattr(
        lifecycle_module.NotificationLifecycleService,
        "_snapshot_group_recipients",
        failure,
    )
    with pytest.raises(RuntimeError, match="snapshot write failed"):
        create(user, groups=group, group_audience_mode="SNAPSHOT")
    assert Notification.objects.count() == before


def test_snapshot_does_not_require_groups_when_only_direct_targets(user: User):
    """A snapshot mode with no groups is harmless and keeps direct recipients."""
    notification = create(
        user,
        recipients=user,
        group_audience_mode="SNAPSHOT",
    )
    assert notification.recipient.filter(pk=user.pk).exists()
    assert Notification.objects.visible_to(user).filter(pk=notification.pk).exists()


def test_snapshot_independent_user_state_survives_group_removal(
    user: User,
    another_user: User,
    group: Group,
) -> None:
    """Membership revocation does not clear a frozen user's personal state."""
    user.groups.add(group)
    another_user.groups.add(group)
    notification = create(
        user,
        groups=group,
        group_audience_mode="SNAPSHOT",
    )
    group.delete()
    assert Notification.objects.set_seen(user, notification.pk, True)
    assert Notification.objects.seen(seen_by=user).filter(pk=notification.pk).exists()
    assert (
        Notification.objects.unseen(unseen_by=another_user)
        .filter(pk=notification.pk)
        .exists()
    )
    Notification.objects.delete_notification(notification.pk, recipient=user)
    assert not Notification.objects.seen(seen_by=user).exists()
    assert (
        Notification.objects.unseen(unseen_by=another_user)
        .filter(pk=notification.pk)
        .exists()
    )


def test_snapshot_policy_is_read_only_in_trusted_serializer(user: User):
    """Even the detailed serializer cannot silently retarget a notification."""
    from django_notification.api.serializers.notification import (
        NotificationSerializer,
    )

    notification = create(user, recipients=user, group_audience_mode="SNAPSHOT")
    serializer = NotificationSerializer(
        notification, data={"group_audience_mode": "DYNAMIC"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    notification.refresh_from_db()
    assert notification.group_audience_mode == GroupAudienceMode.SNAPSHOT
