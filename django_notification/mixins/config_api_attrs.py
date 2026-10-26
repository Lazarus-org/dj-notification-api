from rest_framework.parsers import BaseParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle

from django_notification.settings.conf import config


class ConfigurableAttrsMixin:
    """A mixin for dynamically configuring API attributes based on settings from the
    config.

    This mixin allows you to configure attributes such as permission classes, filter classes,
    pagination, and throttling for the API views. It reads configurations from the `config`
    settings and applies them to the view.

    Attributes:
        ordering_fields (Optional[List[str]]): List of fields by which the API can be ordered.
        search_fields (Optional[List[str]]): List of fields by which the API can be searched.
        parser_classes (List[Type[BaseParser]]): List of parsers to be used for parsing request data.
        permission_classes (List[Type[BasePermission]]): List of permission classes to be used for authorization.
        filterset_class (Optional[Type[BaseFilterSet]]): The filter set class to be used for filtering queryset.
        pagination_class (Optional[Type[BasePagination]]): The pagination class to be used for paginating results.
        throttle_classes (Optional[List[Type[BaseThrottle]]]): List of throttle classes to be used for rate limiting.

    """

    def configure_attrs(self) -> None:
        """Configures API attributes dynamically based on settings from the `config`.

        This method sets the following attributes:
        - `ordering_fields`: Configured based on `config.api_ordering_fields`.
        - `search_fields`: Configured based on `config.api_search_fields`.
        - `parser_classes`: Configured based on `config.api_parser_classes`.
        - `permission_classes`: Configured to include IsAuthenticated by default and optionally additional permission classes.
        - `filterset_class`: Configured based on `config.api_filterset_class`.
        - `pagination_class`: Configured based on `config.api_pagination_class`.
        - `throttle_classes`: Configured based on `config.api_throttle_class`.

        """
        self.ordering_fields: list[str] | None = config.api_ordering_fields
        self.search_fields: list[str] | None = config.api_search_fields
        self.parser_classes: list[type[BaseParser]] = (
            config.api_parser_classes or api_settings.DEFAULT_PARSER_CLASSES
        )

        # DRF supplies @action(permission_classes=...) via view initkwargs.
        # Never replace an action-specific permission with the configured
        # defaults: doing so would remove IsAdminUser from hard-delete routes.
        # Authentication and the project's extra permission are mandatory for
        # both ordinary routes and action-specific routes.
        action_permissions = self.__dict__.get(
            "permission_classes", getattr(type(self), "permission_classes", ())
        )
        permissions: list[type[BasePermission]] = [IsAuthenticated]
        if config.api_extra_permission_class:
            permissions.append(config.api_extra_permission_class)
        for permission in action_permissions:
            if permission is not AllowAny and permission not in permissions:
                permissions.append(permission)
        self.permission_classes = permissions

        if config.api_filterset_class:
            self.filterset_class = config.api_filterset_class

        if config.api_pagination_class:
            self.pagination_class = config.api_pagination_class

        if config.api_throttle_class:
            self.throttle_classes: list[type[BaseThrottle]] | None = [
                config.api_throttle_class
            ]
