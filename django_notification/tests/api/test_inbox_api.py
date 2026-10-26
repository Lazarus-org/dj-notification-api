"""Phase 5 inbox API and per-user notification-state regressions."""

from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.models import (
    DeletedNotification,
    Notification,
    NotificationSeen,
)
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_throttle(monkeypatch):
    """Rate limits are tested separately; API behavior must be deterministic."""
    monkeypatch.setattr(config, "api_throttle_class", None)


def client(user):
    """Return an authenticated API client."""
    result = APIClient()
    result.force_authenticate(user=user)
    return result


def detail(name, obj):
    """Generate a detail-action URL."""
    return reverse(name, kwargs={"pk": obj.pk})


def test_summary_counts_scoped_group_direct_and_read_states(
    user: User,
    another_user: User,
    admin_user: User,
    group: Group,
    notification: Notification,
):
    """Counts deduplicate overlapping group/direct target and isolate users."""
    user.groups.add(group)
    another_user.groups.add(group)
    notification.group.add(group)
    notification.recipient.add(user)
    seen = Notification.objects.create_notification(
        verb="seen",
        actor=user,
        is_sent=True,
        recipients=[user],
    )
    Notification.objects.create_notification(
        verb="unsent",
        actor=user,
        is_sent=False,
        recipients=[user],
    )
    seen.mark_as_seen(user)
    r = client(user).get(reverse("notifications-summary"))
    assert r.status_code == 200
    assert r.data == {"total_count": 2, "read_count": 1, "unread_count": 1}

    group_response = client(another_user).get(reverse("notifications-summary"))
    assert group_response.data == {"total_count": 1, "read_count": 0, "unread_count": 1}
    assert client(admin_user).get(reverse("notifications-summary")).data == {
        "total_count": 0,
        "read_count": 0,
        "unread_count": 0,
    }
    user.groups.remove(group)
    assert client(user).get(reverse("notifications-summary")).data == {
        "total_count": 2,
        "read_count": 1,
        "unread_count": 1,
    }
    # Revoke the only direct path to the group-only notification.
    notification.recipient.remove(user)
    assert client(user).get(reverse("notifications-summary")).data == {
        "total_count": 1,
        "read_count": 1,
        "unread_count": 0,
    }


def test_preview_never_marks_seen_even_for_group_member(
    user: User,
    group: Group,
    notification: Notification,
):
    """New safe GET supports preview without the legacy retrieve side effect."""
    user.groups.add(group)
    notification.group.add(group)
    api = client(user)
    url = detail("notifications-preview", notification)
    assert api.get(url).status_code == 200
    assert api.get(url).status_code == 200
    assert not NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()


def test_explicit_read_unread_actions_are_idempotent_and_user_scoped(
    user: User,
    another_user: User,
    group: Group,
    notification: Notification,
):
    """Direct/group users independently mark one notification read or unread."""
    user.groups.add(group)
    another_user.groups.add(group)
    notification.group.add(group)
    first = client(user)
    for changed in (True, False):
        response = first.post(detail("notifications-mark-seen", notification))
        assert response.status_code == 200
        assert response.data["changed"] is changed
    assert (
        NotificationSeen.objects.filter(notification=notification, user=user).count()
        == 1
    )
    assert (
        client(another_user).get(reverse("notifications-summary")).data["unread_count"]
        == 1
    )
    for changed in (True, False):
        response = first.post(detail("notifications-mark-unseen", notification))
        assert response.status_code == 200
        assert response.data["changed"] is changed
    assert not NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()


def test_explicit_action_does_not_expose_foreign_or_group_revoked_id(
    user: User,
    another_user: User,
    group: Group,
    notification: Notification,
):
    """Staff status is never an authority source for personal state changes."""
    user.groups.add(group)
    notification.group.add(group)
    assert (
        client(another_user)
        .post(detail("notifications-mark-seen", notification))
        .status_code
        == 404
    )
    user.groups.remove(group)
    assert (
        client(user).post(detail("notifications-mark-seen", notification)).status_code
        == 404
    )
    assert not NotificationSeen.objects.filter(notification=notification).exists()


def test_bulk_validation_and_atomic_non_disclosing_404(
    user: User,
    another_user: User,
    notification: Notification,
):
    """A foreign ID causes full rollback rather than partial marking."""
    notification.recipient.add(user)
    foreign = Notification.objects.create_notification(
        verb="foreign",
        actor=user,
        is_sent=True,
        recipients=[another_user],
    )
    url = reverse("notifications-bulk-mark-seen")
    api = client(user)
    for bad in ({"ids": []}, {"ids": [0]}, {"ids": [1] * 501}, {}):
        assert api.post(url, bad, format="json").status_code == 400
    response = api.post(url, {"ids": [notification.pk, foreign.pk]}, format="json")
    assert response.status_code == 404
    assert not NotificationSeen.objects.filter(user=user).exists()
    success = api.post(url, {"ids": [notification.pk, notification.pk]}, format="json")
    assert success.status_code == 200
    assert success.data["processed"] == 1
    assert NotificationSeen.objects.filter(user=user).count() == 1
    reverse_response = api.post(
        reverse("notifications-bulk-mark-unseen"),
        {"ids": [notification.pk]},
        format="json",
    )
    assert reverse_response.status_code == 200
    assert not NotificationSeen.objects.filter(user=user).exists()


def test_selected_bulk_clear_requires_seen_records_and_is_atomic(
    user: User,
    group: Group,
    notification: Notification,
):
    """Bulk clear rejects unseen activity IDs and never deletes notification rows."""
    user.groups.add(group)
    notification.group.add(group)
    unseen = Notification.objects.create_notification(
        verb="unseen",
        actor=user,
        is_sent=True,
        recipients=[user],
    )
    notification.mark_as_seen(user)
    api = client(user)
    url = reverse("activities-bulk-clear")
    assert (
        api.post(url, {"ids": [notification.pk, unseen.pk]}, format="json").status_code
        == 404
    )
    assert not DeletedNotification.objects.filter(user=user).exists()
    ok = api.post(url, {"ids": [notification.pk]}, format="json")
    assert ok.status_code == 200
    assert ok.data["processed"] == 1
    assert DeletedNotification.objects.filter(
        notification=notification, user=user
    ).exists()
    assert Notification.objects.filter(pk=notification.pk).exists()
    assert api.post(url, {"ids": [notification.pk]}, format="json").status_code == 404


def test_canonical_delete_and_safe_post_legacy_actions(
    user: User,
    notification: Notification,
):
    """POST/DELETE alternatives keep old path names where practical."""
    notification.recipient.add(user)
    api = client(user)
    seen = api.post(reverse("notifications-mark-all-as-seen"))
    assert seen.status_code == 200
    assert NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()
    deleted = api.delete(detail("activities-detail", notification))
    assert deleted.status_code == 204
    assert DeletedNotification.objects.filter(
        notification=notification, user=user
    ).exists()
    assert Notification.objects.filter(pk=notification.pk).exists()


def test_legacy_get_can_be_disabled_without_blocking_modern_methods(
    user: User,
    notification: Notification,
):
    """Opt-out returns 405 for unsafe GET; new write methods remain valid."""
    notification.recipient.add(user)
    api = client(user)
    with patch.object(config, "api_allow_legacy_get_mutations", False):
        url = reverse("notifications-mark-all-as-seen")
        assert api.get(url).status_code == 405
        assert not NotificationSeen.objects.filter(user=user).exists()
        assert api.post(url).status_code == 200
        assert (
            api.get(detail("activities-clear-notification", notification)).status_code
            == 405
        )
        assert (
            api.delete(
                detail("activities-clear-notification", notification)
            ).status_code
            == 204
        )


def test_legacy_mutating_get_advertises_deprecation(
    user: User,
    notification: Notification,
):
    """Legacy clients retain GET until opt-out, with explicit deprecation headers."""
    notification.recipient.add(user)
    r = client(user).get(reverse("notifications-mark-all-as-seen"))
    assert r.status_code == 200
    assert r["Deprecation"] == "true"
    assert r["Cache-Control"] == "no-store"


def test_retrieve_auto_seen_setting_can_disable_legacy_side_effect(
    user: User,
    notification: Notification,
):
    """Retrieval can become read-only without changing URL or output schema."""
    notification.recipient.add(user)
    with patch.object(config, "api_retrieve_marks_seen", False):
        url = detail("notifications-detail", notification)
        assert client(user).get(url).status_code == 200
        assert client(user).get(url).status_code == 200
    assert not NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()


def test_anonymous_requests_cannot_use_inbox_actions(notification: Notification):
    """All new actions inherit IsAuthenticated from configurable views."""
    api = APIClient()
    assert api.get(reverse("notifications-summary")).status_code in (401, 403)
    assert api.post(detail("notifications-mark-seen", notification)).status_code in (
        401,
        403,
    )


def test_disabling_legacy_get_mutations_makes_detail_read_only(
    user: User,
    notification: Notification,
):
    """Disabling unsafe GET mutations also covers the old detail read side effect."""
    notification.recipient.add(user)
    with patch.object(config, "api_allow_legacy_get_mutations", False):
        response = client(user).get(detail("notifications-detail", notification))
    assert response.status_code == 200
    assert not NotificationSeen.objects.filter(
        notification=notification, user=user
    ).exists()
