from typing import List, Optional, Union

from django.contrib.auth.models import Group
from django.db.models import JSONField, Model, Q, QuerySet

from django_notification.utils.user_model import UserModel

# Type Alias for Notification QuerySet
Recipient = Optional[UserModel]
Recipients = Optional[Union[UserModel, QuerySet, List[UserModel]]]
Groups = Optional[Union[Group, QuerySet, List[Group]]]
OptConditions = Optional[Q]
Link = Optional[str]
Actor = Model
Target = Optional[Model]
ActionObject = Optional[Model]
Data = Optional[JSONField]
Description = Optional[str]
