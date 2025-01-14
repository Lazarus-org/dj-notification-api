import sys

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType

from django_notification.models import Notification
from django_notification.models.helper.enums.status_choices import NotificationStatus
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.models,
    pytest.mark.models_notification,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestNotification:
    """
    Test suite for the `Notification` model, covering its fields, methods, and string representation.
    """

    def test_notification_fields(self, notification: Notification, user: User) -> None:
        """
        Test that the basic fields of the `Notification` model are correctly set.

        Asserts:
        -------
            - The `verb` field is set correctly.
            - The `actor` field is set to the correct user.
            - The `description` field is set correctly.
            - The `status` field is set to `NotificationStatus.INFO`.
            - The `recipient` and `group` fields are empty.
        """
        assert notification.verb == "liked"
        assert notification.actor == user
        assert notification.description == "User liked a post"
        assert notification.status == NotificationStatus.INFO
        assert notification.recipient.count() == 0
        assert notification.group.count() == 0

    def test_title_generator_with_target_and_action_object(
        self, notification: Notification, user_content_type: ContentType, user: User
    ) -> None:
        """
        Test the title generator when both a target and an action object are present.

        Asserts:
        -------
            - The generated title matches the expected format when both target and action object are set.
        """
        notification.target_content_type = user_content_type
        notification.target_object_id = user.id
        notification.action_object_content_type = user_content_type
        notification.action_object_object_id = user.id
        title = notification._title_generator()

        assert title == f"{user} liked {user} on {user}"

    def test_title_generator_action_object_without_target(
        self, notification: Notification, user_content_type: ContentType, user: User
    ) -> None:
        """
        Test the title generator when there is an action object but no target.

        Asserts:
        -------
            - The generated title matches the expected format when only an action object is set.
        """
        notification.action_object_content_type = user_content_type
        notification.action_object_object_id = user.id
        title = notification._title_generator()

        assert title == f"{user} liked {user}"

    def test_title_generator_with_only_target(
        self, notification: Notification, user_content_type: ContentType, user: User
    ) -> None:
        """
        Test the title generator when only a target is present.

        Asserts:
        -------
            - The generated title matches the expected format when only a target is set.
        """
        notification.target_content_type = user_content_type
        notification.target_object_id = user.id
        title = notification._title_generator()

        assert title == f"{user} liked {user}"

    def test_title_generator_with_no_target_or_action_object(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test the title generator when neither target nor action object are present.

        Asserts:
        -------
            - The generated title matches the expected format when neither target nor action object is set.
        """
        title = notification._title_generator()
        assert title == f"{user} liked"

    def test_mark_as_seen(self, notification: Notification, user: User) -> None:
        """
        Test the `mark_as_seen` method to ensure a recipient can mark a notification as seen.

        Asserts:
        -------
            - The recipient is correctly marked as having seen the notification.
        """
        notification.recipient.add(user)
        notification.mark_as_seen(user)

        assert notification.seen_by.filter(id=user.id).exists()

    def test_mark_as_seen_with_group(
        self, notification: Notification, user: User, group: Group
    ) -> None:
        """
        Test the `mark_as_seen` method when the user belongs to a group that is a recipient.

        Asserts:
        -------
            - The recipient user is correctly marked as having seen the notification through their group.
        """
        user.groups.add(group)
        notification.group.add(group)
        notification.mark_as_seen(user)

        assert notification.seen_by.filter(id=user.id).exists()

    def test_mark_as_seen_without_permission(self, notification, another_user):
        """
        Test that an unauthorized user cannot mark a notification as seen.

        Asserts:
        -------
            - A `PermissionError` is raised when an unauthorized user attempts to mark a notification as seen.
        """
        with pytest.raises(PermissionError, match="don't have permission"):
            notification.mark_as_seen(another_user)

    def test_notification_str_representation(self, notification: Notification) -> None:
        """
        Test the string representation of a notification.

        Asserts:
        -------
            - The string representation matches the expected format.
        """
        expected_str = f"{notification.description} now"
        assert str(notification) == expected_str

    def test_add_recipients_to_notification(
        self, notification: Notification, user: User
    ) -> None:
        """
        Test adding recipients to the notification.

        Asserts:
        -------
            - The recipient is correctly added to the notification.
        """
        notification.recipient.add(user)
        assert notification.recipient.filter(id=user.id).exists()

    def test_add_groups_to_notification(
        self, notification: Notification, group: Group
    ) -> None:
        """
        Test adding groups to the notification.

        Asserts:
        -------
            - The group is correctly added to the notification.
        """
        notification.group.add(group)
        assert notification.group.filter(id=group.id).exists()

    def test_notification_data_field(self, notification: Notification) -> None:
        """
        Test the `data` field of a notification, ensuring it can store and retrieve JSON data.

        Asserts:
        -------
            - The `data` field stores and retrieves JSON data correctly.
        """
        notification.data = {"key": "value"}
        notification.save()

        assert notification.data == {"key": "value"}

    def test_default_field_values(self, notification: Notification) -> None:
        """
        Test the default values of the boolean fields in a notification.

        Asserts:
        -------
            - The `is_sent` and `public` fields have default values of `True`.
        """
        assert notification.is_sent is True
        assert notification.public is True
