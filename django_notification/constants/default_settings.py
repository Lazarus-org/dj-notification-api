from dataclasses import dataclass, field
from typing import List, Optional, Type

from rest_framework.permissions import BasePermission

from django_notification.utils.user_model import USERNAME_FIELD, REQUIRED_FIELDS


@dataclass(frozen=True)
class DefaultAPISettings:
    include_soft_delete: bool = True
    include_hard_delete: bool = False
    allow_list: bool = True
    allow_retrieve: bool = True
    include_serializer_full_details: bool = False
    user_serializer_fields: List[str] = field(
        default_factory=lambda: [USERNAME_FIELD] + list(REQUIRED_FIELDS)
    )
    user_serializer_class: Optional[str] = None
    group_serializer_class: Optional[str] = None
    authenticated_user_throttle_rate: str = "30/minute"
    staff_user_throttle_rate: str = "100/minute"
    throttle_class: str = (
        "notification.api.throttlings.role_base_throttle.RoleBasedUserRateThrottle"
    )
    pagination_class: str = (
        "notification.api.paginations.limit_offset_pagination.DefaultLimitOffSetPagination"
    )
    filterset_class: str = (
        "notification.api.filters.notification_filter.NotificationFilter"
    )
    extra_permission_class: Optional[Type[BasePermission]] = None

    ordering_fields: List[str] = field(
        default_factory=lambda: ["id", "timestamp", "email_sent", "public"]
    )
    search_fields: List[str] = field(default_factory=lambda: ["verb", "description"])
