from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class NotificationStatus(TextChoices):
    ERROR = 'ERROR', _('Error - Indicates critical errors that require immediate attention')
    SUCCESS = 'SUCCESS', _('Success - Indicates successful completion of an operation')
    WARNING = 'WARNING', _('Warning - Indicates potential issues or concerns that should be addressed')
    INFO = 'INFO', _('Information - Provides general informational messages')
    CRITICAL = 'CRITICAL', _('Critical - Indicates critical issues that may impact functionality')
    SENSITIVE = 'SENSITIVE', _('Sensitive - Indicates notifications related to sensitive data')
    INFRASTRUCTURE = 'INFRASTRUCTURE', _('Infrastructure - Indicates notifications related to system infrastructure')
