"""Production defaults must keep safe HTTP methods free of state changes."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from django_notification.constants.default_settings import DefaultAPISettings
from django_notification.models import Notification, NotificationSeen
from django_notification.settings.conf import config


@pytest.mark.django_db
def test_production_defaults_block_cross_site_get_mutations_and_require_csrf(user):
    defaults = DefaultAPISettings()
    assert defaults.allow_legacy_get_mutations is False
    assert defaults.retrieve_marks_seen is False
    item = Notification.objects.create_notification(
        actor=user,
        verb="Safe read",
        recipients=[user],
        is_sent=True,
    )
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    with (
        patch.object(
            config,
            "api_allow_legacy_get_mutations",
            defaults.allow_legacy_get_mutations,
        ),
        patch.object(config, "api_retrieve_marks_seen", defaults.retrieve_marks_seen),
    ):
        assert (
            client.get(reverse("notifications-detail", args=[item.pk])).status_code
            == 200
        )
        assert client.get(reverse("notifications-mark-all-as-seen")).status_code == 405
        assert (
            client.post(
                reverse("notifications-mark-seen", args=[item.pk]), {}
            ).status_code
            == 403
        )
        assert not NotificationSeen.objects.filter(
            notification=item, user=user
        ).exists()
