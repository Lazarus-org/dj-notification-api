Customize the API safely
=========================

Customize presentation and application policy without changing who can read
a notification. Keep the built-in personal visibility selection and avoid
serializing global recipient/read-state relationships.

A custom list serializer
--------------------------

Create an application module, for example ``myapp/notification_serializers.py``::

    from rest_framework import serializers
    from django_notification.models import Notification

    class InboxListSerializer(serializers.ModelSerializer):
        urgent = serializers.SerializerMethodField()

        class Meta:
            model = Notification
            fields = (
                "id", "verb", "description", "category",
                "priority", "urgent", "timestamp",
            )

        def get_urgent(self, notification):
            return notification.priority == "URGENT"

Configure the import path before Django starts::

    DJANGO_NOTIFICATION_SERIALIZER_CLASS = (
        "myapp.notification_serializers.InboxListSerializer"
    )
    DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS = False

Both personal list views pass Notification instances to this serializer.
Detail and preview retain the package's personal full representation.
If your client needs category/priority without a custom derived field, the
built-in full-details switch or a field projection is simpler.

Do not include ``recipient``, ``group``, ``seen_by`` or arbitrary ``data``
just because the requester can read the notification. One recipient may not
be entitled to learn who else received or read it. The trusted
NotificationSerializer is designed for administrative integrations, not
personal list replacement.

Add an application permission
-------------------------------

For an application that requires a verified account, supply an additional
DRF permission. This example assumes your user model exposes
``email_verified``::

    # myapp/notification_permissions.py
    from rest_framework.permissions import BasePermission

    class HasVerifiedEmail(BasePermission):
        message = "Verify your email address before using notifications."

        def has_permission(self, request, view):
            return bool(getattr(request.user, "email_verified", False))

    # settings.py
    DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS = (
        "myapp.notification_permissions.HasVerifiedEmail"
    )

This class runs alongside authentication and action permissions; it does
not replace recipient checks or remove staff-only guards on permanent
deletion. Keep object access in the existing queryset. A global permission
returning True is not permission to view every notification.

Filter by message status
-------------------------

Built-in category/priority filters need no optional filterset configuration.
To add status filtering without exposing recipient relationships, define::

    # myapp/notification_filters.py
    from django_filters import rest_framework as filters
    from django_notification.models import Notification

    class InboxFilter(filters.FilterSet):
        class Meta:
            model = Notification
            fields = ["status"]

Add ``django_filters`` to INSTALLED_APPS and configure::

    DJANGO_NOTIFICATION_API_FILTERSET_CLASS = (
        "myapp.notification_filters.InboxFilter"
    )

Clients can now request
``GET /notification/notifications/?status=WARNING``. The filter is applied
after personal eligibility selection. It cannot grant access to unrelated
messages.

The bundled filterset is available at
``django_notification.api.filters.notification_filter.NotificationFilter``.
It additionally exposes status/public, timestamp ranges, group IDs and
recipient IDs. Use a narrower application filterset when recipient/group
filters are inappropriate for your clients.

Build a custom application view
---------------------------------

When your own Django view needs notifications, compose eligibility explicitly::

    from django_notification.models import Notification

    def unread_for(user):
        return (
            Notification.objects.visible_to(user)
            .active_at()
            .sent_only()
            .not_deleted_by(user)
            .unseen_by(user)
            .order_by("-timestamp", "-pk")
        )

Use ``Notification.objects.set_seen(user, id, seen=True)`` rather than
writing NotificationSeen directly. The manager preserves access checks,
idempotent behavior and event emission. If subclassing package viewsets,
retain their authentication, action permissions and scoped querysets.

Avoid per-row queries in serializers. The compact built-in representation
does not need recipient/group prefetching. A trusted serializer that traverses
relations should prefetch them deliberately and keep responses bounded.
Test queries with multiple recipients, multiple groups and multiple rows,
rather than only one notification.

Application-owned transport adapters
--------------------------------------

A custom SMS/push adapter subclasses DeliveryBackend and implements
``send(delivery, *, idempotency_key)``. The adapter resolves the recipient's
current destination from your own profile/token model and calls your chosen
provider. No phone-number field, token schema or provider SDK is imposed by
the package.

Return normally only when the provider accepts the request. Raise
RetryableDeliveryError for a transient failure or PermanentDeliveryError for
invalid destinations and permanent rejections. Never persist/log raw provider
response text or credentials. Pass the supplied idempotency key through to
providers supporting duplicate suppression.

Use ``render_delivery(delivery)`` to opt into the package template catalog.
A custom adapter that does not call it owns its rendering behavior.
See :doc:`delivery` for a complete local backend and the worker contract.
