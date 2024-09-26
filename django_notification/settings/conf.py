from typing import Any, List, Optional, Type, Union

from django.conf import settings
from django.utils.module_loading import import_string

from django_notification.constants.default_settings import (
    DefaultAdminSettings,
    DefaultAPISettings,
    DefaultPaginationAndFilteringSettings,
    DefaultSerializerSettings,
    DefaultThrottleSettings,
)


# pylint: disable=too-many-instance-attributes
class NotificationConfig:
    """A configuration handler for the Django Notification API, allowing
    settings to be dynamically loaded from Django settings with defaults
    provided through `DefaultAPISettings`.

    Attributes:
        include_soft_delete (bool): Whether soft delete is enabled for notifications.
        include_hard_delete (bool): Whether hard delete is enabled for notifications.
        include_serializer_full_details (bool): Whether full details are included in the serializer.
        api_allow_list (bool): Whether the API allows listing notifications.
        api_allow_retrieve (bool): Whether the API allows retrieving single notifications.
        user_serializer_fields (List[str]): Fields included in the user serializer.
        user_serializer_class (Optional[Type[Any]]): The class used for User serialization.
        group_serializer_class (Optional[Type[Any]]): The class used for Group serialization.
        authenticated_user_throttle_rate (str): Throttle rate for authenticated users.
        staff_user_throttle_rate (str): Throttle rate for staff users.
        api_throttle_class (Optional[Type[Any]]): The class used for request throttling.
        api_pagination_class (Optional[Type[Any]]): The class used for pagination.
        api_extra_permission_class (Optional[Type[Any]]): An additional permission class.
        api_filterset_class (Optional[Type[Any]]): The class used for filtering.
        api_ordering_fields (List[str]): Fields that can be used for ordering.
        api_search_fields (List[str]): Fields that can be searched.

    """

    prefix = "DJANGO_NOTIFICATION_"

    default_api_settings: DefaultAPISettings = DefaultAPISettings()
    default_serializer_settings: DefaultSerializerSettings = DefaultSerializerSettings()
    default_admin_settings: DefaultAdminSettings = DefaultAdminSettings()
    default_pagination_and_filter_settings: DefaultPaginationAndFilteringSettings = (
        DefaultPaginationAndFilteringSettings()
    )
    default_throttle_settings: DefaultThrottleSettings = DefaultThrottleSettings()

    def __init__(self) -> None:
        """Initialize the NotificationConfig, loading values from Django
        settings or falling back to the default API settings."""
        self.include_soft_delete: bool = self.get_setting(
            f"{self.prefix}API_INCLUDE_SOFT_DELETE",
            self.default_api_settings.include_soft_delete,
        )
        self.include_hard_delete: bool = self.get_setting(
            f"{self.prefix}API_INCLUDE_HARD_DELETE",
            self.default_api_settings.include_hard_delete,
        )
        self.admin_has_add_permission: bool = self.get_setting(
            f"{self.prefix}ADMIN_HAS_ADD_PERMISSION",
            self.default_admin_settings.admin_has_add_permission,
        )
        self.admin_has_change_permission: bool = self.get_setting(
            f"{self.prefix}ADMIN_HAS_CHANGE_PERMISSION",
            self.default_admin_settings.admin_has_change_permission,
        )
        self.admin_has_delete_permission: bool = self.get_setting(
            f"{self.prefix}ADMIN_HAS_DELETE_PERMISSION",
            self.default_admin_settings.admin_has_delete_permission,
        )

        self.include_serializer_full_details: bool = self.get_setting(
            f"{self.prefix}SERIALIZER_INCLUDE_FULL_DETAILS",
            self.default_api_settings.include_serializer_full_details,
        )

        self.api_allow_list: bool = self.get_setting(
            f"{self.prefix}API_ALLOW_LIST", self.default_api_settings.allow_list
        )
        self.api_allow_retrieve: bool = self.get_setting(
            f"{self.prefix}API_ALLOW_RETRIEVE",
            self.default_api_settings.allow_retrieve,
        )
        self.user_serializer_fields: List[str] = self.get_setting(
            f"{self.prefix}USER_SERIALIZER_FIELDS",
            self.default_serializer_settings.user_serializer_fields,
        )
        self.user_serializer_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}USER_SERIALIZER_CLASS",
            self.default_serializer_settings.user_serializer_class,
        )
        self.group_serializer_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}GROUP_SERIALIZER_CLASS",
            self.default_serializer_settings.group_serializer_class,
        )
        self.authenticated_user_throttle_rate: str = self.get_setting(
            f"{self.prefix}AUTHENTICATED_USER_THROTTLE_RATE",
            self.default_throttle_settings.authenticated_user_throttle_rate,
        )
        self.staff_user_throttle_rate: str = self.get_setting(
            f"{self.prefix}STAFF_USER_THROTTLE_RATE",
            self.default_throttle_settings.staff_user_throttle_rate,
        )
        self.api_throttle_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}API_THROTTLE_CLASS",
            self.default_throttle_settings.throttle_class,
        )
        self.api_pagination_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}API_PAGINATION_CLASS",
            self.default_pagination_and_filter_settings.pagination_class,
        )
        self.api_extra_permission_class: Optional[
            Type[Any]
        ] = self.get_optional_classes(
            f"{self.prefix}API_EXTRA_PERMISSION_CLASS",
            self.default_api_settings.extra_permission_class,
        )
        self.api_parser_classes: Optional[List[Type[Any]]] = self.get_optional_classes(
            f"{self.prefix}API_PARSER_CLASSES",
            self.default_api_settings.parser_classes,
        )
        self.api_filterset_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}API_FILTERSET_CLASS",
            self.default_pagination_and_filter_settings.filterset_class,
        )
        self.api_ordering_fields: List[str] = self.get_setting(
            f"{self.prefix}API_ORDERING_FIELDS",
            self.default_pagination_and_filter_settings.ordering_fields,
        )
        self.api_search_fields: List[str] = self.get_setting(
            f"{self.prefix}API_SEARCH_FIELDS",
            self.default_pagination_and_filter_settings.search_fields,
        )
        self.admin_site_class: Optional[Type[Any]] = self.get_optional_classes(
            f"{self.prefix}ADMIN_SITE_CLASS",
            self.default_admin_settings.admin_site_class,
        )

    def get_setting(self, setting_name: str, default_value: Any) -> Any:
        """Retrieve a setting from Django settings with a default fallback.

        Args:
            setting_name (str): The name of the setting to retrieve.
            default_value (Any): The default value to return if the setting is not found.

        Returns:
            Any: The value of the setting or the default value if not found.

        """
        return getattr(settings, setting_name, default_value)

    def get_optional_classes(
        self,
        setting_name: str,
        default_path: Optional[Union[str, List[str]]],
    ) -> Optional[Union[Type[Any], List[Type[Any]]]]:
        """Dynamically load a class based on a setting, or return None if the
        setting is None or invalid.

        Args:
            setting_name (str): The name of the setting for the class path.
            default_path (Optional[Union[str, List[str]]): The default import path for the class.

        Returns:
            Optional[Union[Type[Any], List[Type[Any]]]]: The imported class or None
             if import fails or the path is invalid.

        """
        class_path: Optional[Union[str, List[str]]] = self.get_setting(
            setting_name, default_path
        )

        if class_path and isinstance(class_path, str):
            try:
                return import_string(class_path)
            except ImportError:
                return None
        elif class_path and isinstance(class_path, list):
            try:
                return [
                    import_string(cls_path)
                    for cls_path in class_path
                    if isinstance(cls_path, str)
                ]
            except ImportError:
                return []

        return None


config = NotificationConfig()
