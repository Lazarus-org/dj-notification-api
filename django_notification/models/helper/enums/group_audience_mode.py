"""Audience resolution strategies for group-addressed notifications."""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class GroupAudienceMode(TextChoices):
    """Whether group eligibility follows membership or creation-time recipients."""

    DYNAMIC = "DYNAMIC", _("Current group membership")
    SNAPSHOT = "SNAPSHOT", _("Members captured at creation")
