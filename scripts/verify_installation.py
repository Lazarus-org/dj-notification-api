"""Smoke-test an installed distribution independently of the source/test setup.

Run with the clean environment's interpreter from outside the repository. Optional
--user-model checks use the disposable host app next to this script.

"""

import argparse
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-model", choices=("CustomUser", "BareUser"))
    parser.add_argument("--require-core-only", action="store_true")
    options = parser.parse_args()
    if options.require_core_only:
        for module in ("channels", "redis", "celery", "daphne", "psycopg"):
            if find_spec(module) is not None:
                raise RuntimeError(
                    f"Core check requires an environment without {module}"
                )

    import django
    from django.conf import settings

    apps = [
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "rest_framework",
        "django_filters",
        "django_notification",
    ]
    extra = {}
    if options.user_model:
        apps.append("validation_app")
        extra["AUTH_USER_MODEL"] = f"validation_app.{options.user_model}"
    with TemporaryDirectory(prefix="djnotify-install-") as temporary:
        settings.configure(
            SECRET_KEY="installation-test-only",
            INSTALLED_APPS=apps,
            DATABASES={
                alias: {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": str(Path(temporary) / f"{alias}.sqlite3"),
                }
                for alias in ("default", "other")
            },
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
            DJANGO_NOTIFICATION_API_EVENT_DELIVERY="outbox",
            **extra,
        )
        django.setup()
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        from django_notification.events import notification_event
        from django_notification.models import Notification, NotificationOutboxEvent
        from django_notification.outbox import OutboxDeliveryService

        call_command("check")
        for alias in ("default", "other"):
            call_command("migrate", database=alias, verbosity=0, interactive=False)
        call_command("makemigrations", "django_notification", check=True, dry_run=True)
        seen = []

        def receiver(sender, event, **kwargs):
            seen.append(event)

        notification_event.connect(receiver, weak=False)
        try:
            for alias in ("default", "other"):
                user = (
                    get_user_model()
                    .objects.db_manager(alias)
                    .create(
                        email=f"{alias}@example.com",
                        **(
                            {"username": alias}
                            if options.user_model != "BareUser"
                            else {}
                        ),
                    )
                )
                item = Notification.objects.db_manager(alias).create_notification(
                    actor=user,
                    verb="Installed",
                    recipients=[user],
                    is_sent=True,
                    idempotency_key="same-key",
                )
                if (
                    Notification.objects.using(alias).visible_to(user).get().pk
                    != item.pk
                ):
                    raise RuntimeError("Installed notification is not visible")
                if not NotificationOutboxEvent.objects.using(alias).exists():
                    raise RuntimeError("Missing durable intent on selected alias")
                if OutboxDeliveryService(database=alias).process_next() != "delivered":
                    raise RuntimeError("Installed outbox did not dispatch")
                from django.contrib.auth.models import Group

                group = Group.objects.using(alias).create(name="host-group")
                if hasattr(user, "groups"):
                    user.groups.add(group)
                    frozen = Notification.objects.db_manager(alias).create_notification(
                        actor=user,
                        verb="Frozen",
                        groups=[group],
                        group_audience_mode="SNAPSHOT",
                        is_sent=True,
                    )
                    dynamic = Notification.objects.db_manager(
                        alias
                    ).create_notification(
                        actor=user,
                        verb="Dynamic",
                        groups=[group],
                        is_sent=True,
                    )
                    user.groups.remove(group)
                    visible = Notification.objects.using(alias).visible_to(user)
                    if (
                        not visible.filter(pk=frozen.pk).exists()
                        or visible.filter(pk=dynamic.pk).exists()
                    ):
                        raise RuntimeError(
                            "Custom-user group audience changed incorrectly"
                        )
                else:
                    before = Notification.objects.using(alias).count()
                    try:
                        Notification.objects.db_manager(alias).create_notification(
                            actor=user,
                            verb="Unsupported snapshot",
                            groups=[group],
                            group_audience_mode="SNAPSHOT",
                        )
                    except ValueError:
                        pass
                    else:
                        raise RuntimeError(
                            "Groupless user incorrectly accepted a group snapshot"
                        )
                    if Notification.objects.using(alias).count() != before:
                        raise RuntimeError("Invalid snapshot left an orphan")
            if {event.database for event in seen} != {"default", "other"}:
                raise RuntimeError("Events crossed database aliases")
            from rest_framework.test import APIRequestFactory, force_authenticate

            from django_notification.api.views.notification import NotificationViewSet
            from django_notification.models import NotificationSeen

            default_user = get_user_model().objects.get(email="default@example.com")
            item = Notification.objects.get(verb="Installed")
            request = APIRequestFactory().get(f"/notifications/{item.pk}/")
            force_authenticate(request, default_user)
            response = NotificationViewSet.as_view({"get": "retrieve"})(
                request, pk=str(item.pk)
            )
            if response.status_code != 200 or NotificationSeen.objects.exists():
                raise RuntimeError("Core REST detail is not a safe authenticated read")
        finally:
            notification_event.disconnect(receiver)
            from django.db import connections

            connections.close_all()
        print(
            f"PASS: installed core, migrations, custom user={options.user_model or 'auth.User'}, two database aliases"
        )


if __name__ == "__main__":
    main()
