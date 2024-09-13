from django.conf import settings
from django.utils.module_loading import import_string

from django_notification.constants.default_settings import DefaultAPISettings


class NotificationAppConfig:
    default_api_settings = DefaultAPISettings()

    def __init__(self):
        self.include_soft_delete = self.get_setting(
            "DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE",
            self.default_api_settings.include_soft_delete,
        )
        self.include_hard_delete = self.get_setting(
            "DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE",
            self.default_api_settings.include_hard_delete,
        )

        self.include_serializer_full_details = self.get_setting(
            "DJANGO_NOTIFICATION_SERIALIZER_INCLUDE_FULL_DETAILS",
            self.default_api_settings.include_serializer_full_details,
        )

        self.api_allow_list = self.get_setting(
            "DJANGO_NOTIFICATION_API_ALLOW_LIST", self.default_api_settings.allow_list
        )
        self.api_allow_retrieve = self.get_setting(
            "DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE",
            self.default_api_settings.allow_retrieve,
        )

        # self.sender_email = self.get_setting(
        #     "DJANGO_NOTIFICATION_EMAIL_HOST_USER", None
        # )

        self.user_serializer_fields = self.get_setting(
            "DJANGO_NOTIFICATION_USER_SERIALIZER_FIELDS",
            self.default_api_settings.user_serializer_fields,
        )

        self.authenticated_user_throttle_rate = self.get_setting(
            "DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE",
            self.default_api_settings.authenticated_user_throttle_rate,
        )
        self.staff_user_throttle_rate = self.get_setting(
            "DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE",
            self.default_api_settings.staff_user_throttle_rate,
        )

        self.api_throttle_class = self.get_optional_class(
            "DJANGO_NOTIFICATION_API_THROTTLE_CLASS",
            self.default_api_settings.throttle_class,
        )
        self.api_pagination_class = self.get_optional_class(
            "DJANGO_NOTIFICATION_API_PAGINATION_CLASS",
            self.default_api_settings.pagination_class,
        )
        self.api_extra_permission_class = self.get_optional_class(
            "DJANGO_NOTIFICATION_API_EXTRA_PERMISSION_CLASS",
            self.default_api_settings.extra_permission_class,
        )

        self.api_filterset_class = self.get_optional_class(
            "DJANGO_NOTIFICATION_API_FILTERSET_CLASS",
            self.default_api_settings.filterset_class,
        )
        self.api_ordering_fields = self.get_setting(
            "DJANGO_NOTIFICATION_API_ORDERING_FIELDS",
            self.default_api_settings.ordering_fields,
        )
        self.api_search_fields = self.get_setting(
            "DJANGO_NOTIFICATION_API_SEARCH_FIELDS",
            self.default_api_settings.search_fields,
        )

    def get_setting(self, setting_name, default_value):
        """
        Retrieve a setting from Django settings with a default fallback.
        """
        return getattr(settings, setting_name, default_value)

    def get_optional_class(self, setting_name, default_path):
        """
        Dynamically load a class based on a setting, or return None if the setting is None or invalid.
        """
        class_path = self.get_setting(setting_name, default_path)

        if class_path and isinstance(class_path, str):
            try:
                return import_string(class_path)
            except ImportError:
                return None
        return None


config = NotificationAppConfig()
