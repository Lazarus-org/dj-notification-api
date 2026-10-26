"""Managed categories, priority, and personal preference regressions."""

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.models import (
    Notification,
    NotificationCategory,
    NotificationPreference,
)
from django_notification.models.helper.enums.group_audience_mode import (
    GroupAudienceMode,
)
from django_notification.models.helper.enums.priority_choices import (
    NotificationPriority,
)
from django_notification.settings.conf import config

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _disable_throttle(monkeypatch):
    """Keep request-rate limits separate from preference behavior."""
    monkeypatch.setattr(config, "api_throttle_class", None)


def client(user):
    """Return a user-authenticated DRF test client."""
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def notification(user, category="general", **kwargs):
    """Create a sent, directly addressed notification."""
    return Notification.objects.create_notification(
        actor=user,
        verb="Preferences test",
        is_sent=True,
        recipients=[user],
        category=category,
        **kwargs,
    )


def category(slug, mandatory=False):
    """Register an optional or mandatory notification category."""
    return NotificationCategory.objects.create(
        slug=slug, name=slug.title(), is_mandatory=mandatory
    )


def pref_url(slug):
    """Resolve the named preference mutation action."""
    return reverse(
        "notifications-set-preference",
        kwargs={
            "category_slug": slug,
        },
    )


def test_general_migration_default_and_existing_creation(user: User):
    """The seeded General category works without new creation arguments."""
    general = NotificationCategory.objects.get(pk="general")
    item = Notification.objects.create_notification(
        actor=user, verb="default", recipients=[user]
    )
    assert general.is_active and not general.is_mandatory
    assert item.category_id == "general"
    assert item.priority == NotificationPriority.NORMAL


def test_unknown_inactive_category_or_priority_rejected_before_write(user: User):
    """Creation rejects nonexistent/inactive categories and invalid priority."""
    category("disabled-topic")
    NotificationCategory.objects.filter(pk="disabled-topic").update(is_active=False)
    for kwargs in (
        {"category": "missing"},
        {"category": "disabled-topic"},
        {"priority": "PANIC"},
    ):
        with pytest.raises(ValueError):
            notification(user, **kwargs)
    assert not Notification.objects.exists()


def test_preference_affects_direct_and_group_feeds_independently(
    user: User,
    another_user: User,
    group: Group,
):
    """Opting out hides direct/group rows only for that user."""
    cat = category("promotions")
    user.groups.add(group)
    another_user.groups.add(group)
    group_notification = Notification.objects.create_notification(
        actor=user,
        verb="promotions",
        groups=[group],
        is_sent=True,
        category=cat.slug,
    )
    direct = notification(user, cat.slug)
    NotificationPreference.objects.create(user=user, category=cat, enabled=False)
    assert (
        not Notification.objects.visible_to(user)
        .filter(pk__in=[direct.pk, group_notification.pk])
        .exists()
    )
    assert (
        Notification.objects.visible_to(another_user)
        .filter(pk=group_notification.pk)
        .exists()
    )
    assert Notification.objects.filter(pk=direct.pk).exists()
    NotificationPreference.objects.filter(user=user, category=cat).delete()
    assert (
        Notification.objects.visible_to(user)
        .filter(pk__in=[direct.pk, group_notification.pk])
        .count()
        == 2
    )


def test_mandatory_overrides_stale_opt_out(user: User):
    """Changing a category to mandatory must restore eligibility immediately."""
    cat = category("safety")
    item = notification(user, cat.slug)
    NotificationPreference.objects.create(user=user, category=cat, enabled=False)
    assert not Notification.objects.visible_to(user).filter(pk=item.pk).exists()
    cat.is_mandatory = True
    cat.save(update_fields=["is_mandatory"])
    assert Notification.objects.visible_to(user).filter(pk=item.pk).exists()


def test_snapshot_audience_and_preferences_are_separate(
    user: User,
    another_user: User,
    group: Group,
):
    """Opt-outs do not change persisted snapshot recipients."""
    cat = category("alerts")
    user.groups.add(group)
    item = Notification.objects.create_notification(
        actor=user,
        verb="snapshot",
        groups=[group],
        is_sent=True,
        category=cat.slug,
        group_audience_mode=GroupAudienceMode.SNAPSHOT,
    )
    NotificationPreference.objects.create(user=user, category=cat, enabled=False)
    user.groups.remove(group)
    another_user.groups.add(group)
    assert item.recipient.filter(pk=user.pk).exists()
    assert not Notification.objects.visible_to(user).filter(pk=item.pk).exists()
    assert not Notification.objects.visible_to(another_user).filter(pk=item.pk).exists()
    NotificationPreference.objects.filter(user=user, category=cat).delete()
    assert Notification.objects.visible_to(user).filter(pk=item.pk).exists()


def test_categories_and_preferences_only_expose_own_state(user: User):
    """Unauthenticated requests fail; lists don't expose other users' state."""
    cat = category("news")
    NotificationPreference.objects.create(user=user, category=cat, enabled=False)
    assert APIClient().get(reverse("notifications-preferences")).status_code in (
        401,
        403,
    )
    result = client(user).get(reverse("notifications-preferences"))
    assert result.status_code == 200
    by_category = {row["category"]: row for row in result.data}
    assert by_category["news"]["enabled"] is False
    assert by_category["general"]["enabled"] is True
    assert "user" not in by_category["news"]
    assert client(user).get(reverse("notifications-categories")).status_code == 200


def test_update_preference_reversible_idempotent_and_user_scoped(
    user: User,
    another_user: User,
):
    """Disabling and re-enabling creates or removes only this user's override."""
    cat = category("product")
    url = pref_url(cat.slug)
    own = client(user)
    for _ in range(2):
        response = own.put(url, {"enabled": False}, format="json")
        assert response.status_code == 200
        assert response.data["enabled"] is False
    assert NotificationPreference.objects.filter(user=user, category=cat).count() == 1
    assert not NotificationPreference.objects.filter(
        user=another_user, category=cat
    ).exists()
    response = own.patch(url, {"enabled": True}, format="json")
    assert response.status_code == 200 and response.data["enabled"] is True
    assert not NotificationPreference.objects.filter(user=user, category=cat).exists()


def test_mandatory_preference_rejects_opt_out_and_invalid_data(user: User):
    """Mandatory policy and strict boolean validation produce 400 responses."""
    cat = category("security", mandatory=True)
    url = pref_url(cat.slug)
    assert client(user).put(url, {"enabled": False}, format="json").status_code == 400
    assert client(user).put(url, {"enabled": "nope"}, format="json").status_code == 400
    assert client(user).put(url, {}, format="json").status_code == 400
    assert not NotificationPreference.objects.filter(user=user).exists()
    assert (
        client(user)
        .put(pref_url("does-not-exist"), {"enabled": False}, format="json")
        .status_code
        == 404
    )


def test_summary_and_category_priority_filters(user: User):
    """Summary filters and personal list honor categories and priority."""
    category("ops")
    item = notification(user, category="ops", priority=NotificationPriority.URGENT)
    notification(user, priority=NotificationPriority.LOW)
    filtered = client(user).get(
        reverse("notifications-summary"), {"category": "ops", "priority": "URGENT"}
    )
    assert filtered.status_code == 200
    assert filtered.data["total_count"] == 1
    listing = client(user).get(
        reverse("notifications-list"), {"category": "ops", "priority": "URGENT"}
    )
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert listing.data["results"][0]["id"] == item.pk
    assert (
        client(user)
        .get(reverse("notifications-list"), {"priority": "INVALID"})
        .status_code
        == 400
    )


def test_keys_do_not_reuse_other_category_or_priority(user: User):
    """Idempotency and deduplication keys include category and priority."""
    category("finance")
    kwargs = dict(recipients=[user], idempotency_key="event:category:1")
    first = Notification.objects.create_notification(
        actor=user, verb="event", category="finance", **kwargs
    )
    assert (
        Notification.objects.create_notification(
            actor=user, verb="event", category="finance", **kwargs
        ).pk
        == first.pk
    )
    with pytest.raises(ValueError, match="different event"):
        Notification.objects.create_notification(
            actor=user, verb="event", category="general", **kwargs
        )
    with pytest.raises(ValueError, match="different event"):
        Notification.objects.create_notification(
            actor=user,
            verb="event",
            category="finance",
            priority=NotificationPriority.URGENT,
            **kwargs,
        )


def test_opt_out_blocks_read_mutations_without_erasing_state(user: User):
    """Preferences gate personal actions but do not destroy previous read state."""
    cat = category("quiet")
    item = notification(user, cat.slug)
    assert Notification.objects.set_seen(user, item.pk, seen=True) is True
    NotificationPreference.objects.create(user=user, category=cat, enabled=False)
    assert client(user).get(reverse("notifications-summary")).data == {
        "total_count": 0,
        "read_count": 0,
        "unread_count": 0,
    }
    from django.http import Http404

    with pytest.raises(Http404):
        Notification.objects.set_seen(user, item.pk, seen=False)
    NotificationPreference.objects.filter(user=user, category=cat).delete()
    assert Notification.objects.visible_to(user).filter(pk=item.pk).exists()
    assert Notification.objects.seen_by(user).filter(pk=item.pk).exists()


def test_category_deactivation_prevents_creation_not_existing_visibility(
    user: User,
):
    """Existing category records stay visible when further creation is disabled."""
    cat = category("archive")
    item = notification(user, cat.slug)
    cat.is_active = False
    cat.save(update_fields=["is_active"])
    assert Notification.objects.visible_to(user).filter(pk=item.pk).exists()
    assert client(user).get(reverse("notifications-preferences")).status_code == 200
    assert "archive" not in {
        row["category"]
        for row in client(user).get(reverse("notifications-categories")).data
    }
    with pytest.raises(ValueError):
        notification(user, cat.slug)
