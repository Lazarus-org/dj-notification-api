import pytest
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType

from django.utils.timezone import now
from django_notification.models import (
    Notification,
    NotificationSeen,
    NotificationRecipient,
    DeletedNotification,
)
from django_notification.models.helper.enums.status_choices import NotificationStatus


from typing import Dict, Any, List


@pytest.fixture
def notification_dict(notification: Notification) -> Dict[str, Any]:
    """
    Fixture to provide a dictionary representation of a given Notification instance.

    Args:
        notification (Notification): The Notification instance to convert.

    Returns:
        Dict[str, Any]: A dictionary containing the notification's id, description,
                        status, link, and timestamp.
    """
    return (
        Notification.objects.filter(pk=notification.id)
        .values(
            "id",
            "description",
            "status",
            "link",
            "timestamp",
        )
        .first()
    )


@pytest.fixture
def notification_seen(db, notification: Notification, user: User) -> NotificationSeen:
    """
    Fixture to create and return a NotificationSeen instance for testing.

    Args:
        db: The database fixture.
        notification (Notification): The Notification instance associated with the seen notification.
        user (User): The user who has seen the notification.

    Returns:
        NotificationSeen: The created NotificationSeen instance.
    """
    notification.recipient.add(user)
    return NotificationSeen.objects.create(
        notification=notification, user=user, seen_at=now()
    )


@pytest.fixture
def notification_recipient(
    db, notification: Notification, user: User
) -> NotificationRecipient:
    """
    Fixture to create and return a NotificationRecipient instance for testing.

    Args:
        db: The database fixture.
        notification (Notification): The Notification instance to which the recipient is associated.
        user (User): The recipient of the notification.

    Returns:
        NotificationRecipient: The created NotificationRecipient instance.
    """
    return NotificationRecipient.objects.create(
        notification=notification, recipient=user
    )


@pytest.fixture
def notification(db, user_content_type: ContentType, user: User) -> Notification:
    """
    Fixture to create and return a Notification instance for testing.

    Args:
        db: The database fixture.
        user_content_type (ContentType): The content type of the user associated with the notification.
        user (User): The user who is the actor of the notification.

    Returns:
        Notification: The created Notification instance.
    """
    return Notification.objects.create(
        verb="liked",
        actor_content_type=user_content_type,
        actor_object_id=user.id,
        description="User liked a post",
        status=NotificationStatus.INFO,
        timestamp=now(),
        is_sent=True,
    )


@pytest.fixture
def notifications(db, user: User, qs_user: User, qs_group: Group) -> List[Notification]:
    """
    Fixture to create and return a list of multiple Notification instances for testing.

    Args:
        db: The database fixture.
        user (User): The user associated with the notifications.
        qs_user (User): Another user to be added as a recipient to the notifications.
        qs_group (Group): A group to be added to the notifications.

    Returns:
        List[Notification]: A list of created Notification instances.
    """
    notifications = [
        Notification(
            verb="verb1",
            actor=user,
            description="description1",
            status="INFO",
            is_sent=True,
            public=True,
            timestamp=now(),
        ),
        Notification(
            verb="verb2",
            actor=user,
            description="description2",
            status="WARNING",
            is_sent=False,
            public=False,
            timestamp=now(),
        ),
        Notification(
            verb="verb3",
            actor=user,
            description="description3",
            status="ERROR",
            is_sent=True,
            public=True,
            timestamp=now(),
        ),
    ]
    notifications = Notification.objects.bulk_create(notifications)
    notifications[0].recipient.add(qs_user)
    notifications[1].recipient.add(qs_user)
    notifications[2].recipient.add(qs_user)

    notifications[0].group.add(qs_group)
    notifications[1].group.add(qs_group)
    notifications[2].group.add(qs_group)

    return notifications


@pytest.fixture
def deleted_notification(
    db, notification: Notification, user: User
) -> DeletedNotification:
    """
    Fixture to create and return a DeletedNotification instance for testing.

    Args:
        db: The database fixture.
        notification (Notification): The Notification instance associated with the deleted notification.
        user (User): The user who has deleted the notification.

    Returns:
        DeletedNotification: The created DeletedNotification instance.
    """
    notification.recipient.add(user)
    return DeletedNotification.objects.create(
        notification=notification, user=user, deleted_at=now()
    )
