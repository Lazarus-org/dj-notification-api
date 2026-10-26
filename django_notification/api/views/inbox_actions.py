"""Shared helpers for the personal inbox's transition away from mutating GETs."""

from rest_framework.exceptions import MethodNotAllowed

from django_notification.api.serializers.inbox import NotificationIdsSerializer
from django_notification.settings.conf import config


def require_mutation_method(request):
    """Allow legacy GET mutations only while explicitly enabled."""
    if request.method == "GET" and not config.api_allow_legacy_get_mutations:
        raise MethodNotAllowed("GET")


def mark_legacy_get_response(request, response):
    """Flag unsafe legacy GET routes to migrating API clients."""
    if request.method == "GET":
        response["Deprecation"] = "true"
        response["Cache-Control"] = "no-store"
    return response


def validated_ids(request):
    """Return distinct positive IDs after strict request-body validation."""
    serializer = NotificationIdsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["ids"]
