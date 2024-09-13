from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoNotificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_notification"
    verbose_name = _("Django Notification")

    def ready(self) -> None:
        """
        This method is called when the application is fully loaded.

        Its main purpose is to perform startup tasks, such as importing
        and registering system checks for validating the configuration
        settings of the `django_notification` app. It ensures that
        all necessary configurations are in place and properly validated
        when the Django project initializes.

        In this case, it imports the settings checks from the
        `django_notification.settings` module to validate the configuration
        settings for notifications.
        """
        from django_notification.settings import checks
