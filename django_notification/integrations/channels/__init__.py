"""Optional Django Channels bridge for notification lifecycle events.

Importing this package does not import Channels or activate any event receiver.
See ``connect_notification_channels`` for explicit application registration.

"""

from .dispatcher import connect_notification_channels, disconnect_notification_channels

__all__ = ["connect_notification_channels", "disconnect_notification_channels"]
