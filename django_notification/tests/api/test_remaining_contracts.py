"""Configured API restrictions and effective schedule representations."""

import pytest
from django.urls import reverse

from django_notification.api.serializers.dynamic_notification import (
    NotificationDynamicSerializer,
)
from django_notification.api.serializers.notification import NotificationSerializer
from django_notification.api.serializers.self_service_notification import (
    NotificationSelfServiceSerializer,
)
from django_notification.models import NotificationDeliverySchedule
from django_notification.settings.conf import config
from django_notification.tests.delivery.test_templates_preferences import (
    _client,
    _notify,
    _url,
)

pytestmark = pytest.mark.django_db


def test_null_fields_can_be_retained(user, monkeypatch):
    notification = _notify(user)
    notification.link = None
    monkeypatch.setattr(config, "exclude_serializer_null_fields", False)
    for serializer in (NotificationSerializer, NotificationSelfServiceSerializer):
        assert serializer(notification).data["link"] is None
    monkeypatch.setattr(config, "notification_serializer_fields", ["title"])
    assert (
        NotificationDynamicSerializer().get_title({"verb": "Legacy"})
        == "{'verb': 'Legacy'}"
    )


def test_runtime_api_restrictions(user, monkeypatch):
    notification = _notify(user)
    notification.mark_as_seen(user)
    client = _client(user)
    monkeypatch.setattr(config, "api_allow_list", False)
    assert client.get(reverse("notifications-summary")).status_code == 405
    monkeypatch.setattr(config, "api_allow_retrieve", False)
    assert (
        client.get(
            reverse("notifications-preview", kwargs={"pk": notification.pk})
        ).status_code
        == 405
    )
    monkeypatch.setattr(config, "include_soft_delete", False)
    assert (
        client.delete(
            reverse("activities-detail", kwargs={"pk": notification.pk})
        ).status_code
        == 405
    )


def test_custom_activity_projection_prefetches_relations(user, monkeypatch):
    from django_notification.api.views.activity import ActivityViewSet
    from types import SimpleNamespace

    notification = _notify(user)
    notification.mark_as_seen(user)
    monkeypatch.setattr(config, "notification_serializer_fields", ["id", "verb"])
    view = ActivityViewSet()
    view.request = SimpleNamespace(user=user, query_params={})
    queryset = view.get_queryset()
    assert "recipient" in queryset._prefetch_related_lookups
    assert list(queryset) == [notification]


def test_schedule_collection_and_new_partial_override(user):
    client = _client(user)
    response = client.get(reverse("notifications-delivery-schedule"))
    assert response.status_code == 200
    assert len(response.data) == 4
    assert all(item["frequency"] == "IMMEDIATE" for item in response.data)
    url = reverse("notifications-set-delivery-schedule", kwargs={"channel": "email"})
    response = client.patch(url, {"timezone": "Europe/Paris"}, format="json")
    assert response.status_code == 200
    assert NotificationDeliverySchedule.objects.get(user=user).frequency == "IMMEDIATE"
    response = client.patch(url, {"frequency": "DAILY"}, format="json")
    assert response.status_code == 200
    schedule = NotificationDeliverySchedule.objects.get(user=user)
    assert schedule.frequency == "DAILY"
    assert schedule.timezone == "Europe/Paris"
    assert NotificationDeliverySchedule.objects.filter(user=user).count() == 1
    response = client.get(reverse("notifications-delivery-schedule"))
    assert (
        next(item for item in response.data if item["channel"] == "email")["timezone"]
        == "Europe/Paris"
    )
    assert (
        client.patch(
            reverse("notifications-set-delivery-schedule", kwargs={"channel": "fax"}),
            {},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.patch(
            _url("missing", "email"), {"enabled": False}, format="json"
        ).status_code
        == 404
    )
