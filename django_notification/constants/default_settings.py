from dataclasses import dataclass, field
from typing import List, Optional

from django_notification.utils.user_model import REQUIRED_FIELDS, USERNAME_FIELD


@dataclass(frozen=True)
class DefaultSerializerSettings:
    notification_serializer_fields: Optional[List[str]] = None
    notification_serializer_class: Optional[str] = None
    user_serializer_fields: List[str] = field(
        default_factory=lambda: [USERNAME_FIELD] + list(REQUIRED_FIELDS)
    )
    user_serializer_class: Optional[str] = None
    group_serializer_class: Optional[str] = None


@dataclass(frozen=True)
class DefaultAdminSettings:
    admin_site_class: Optional[str] = None
    admin_has_add_permission: bool = False
    admin_has_change_permission: bool = False
    admin_has_delete_permission: bool = False


@dataclass(frozen=True)
class DefaultThrottleSettings:
    authenticated_user_throttle_rate: str = "30/minute"
    staff_user_throttle_rate: str = "100/minute"
    throttle_class: str = (
        "django_notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"
    )


@dataclass(frozen=True)
class DefaultPaginationAndFilteringSettings:
    pagination_class: str = (
        "django_notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"
    )
    filterset_class: Optional[str] = None
    ordering_fields: List[str] = field(
        default_factory=lambda: ["id", "timestamp", "public"]
    )
    search_fields: List[str] = field(default_factory=lambda: ["verb", "description"])


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class DefaultAPISettings:
    include_soft_delete: bool = True
    include_hard_delete: bool = False
    allow_list: bool = True
    allow_retrieve: bool = True
    include_serializer_full_details: bool = False
    exclude_serializer_none_fields: bool = False
    extra_permission_class: Optional[str] = None
    parser_classes: List[str] = field(
        default_factory=lambda: [
            "rest_framework.parsers.JSONParser",
            "rest_framework.parsers.MultiPartParser",
            "rest_framework.parsers.FormParser",
        ]
    )
