"""Input validation for bounded personal notification bulk actions."""

from rest_framework import serializers


# Input-only serializer; lifecycle services own persistence.
# pylint: disable-next=abstract-method
class NotificationIdsSerializer(serializers.Serializer):
    """Accept a nonempty, bounded list of positive notification IDs."""

    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=500,
    )

    def validate_ids(self, values):
        """Deduplicate repeated IDs while preserving request order."""
        return list(dict.fromkeys(values))
