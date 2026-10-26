"""Optional external notification delivery backends and durable workers.

No external provider client is imported when the core package is loaded. Enable
explicitly with ``connect_notification_delivery`` in AppConfig.ready().

"""

from .registry import connect_notification_delivery, disconnect_notification_delivery

__all__ = ("connect_notification_delivery", "disconnect_notification_delivery")
