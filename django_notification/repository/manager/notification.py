from typing import Optional

from django.contrib.auth.models import Group
from django.db.models import Manager, Q, QuerySet

from django_notification.constants.qs_types import (
    ActionObject,
    Actor,
    Data,
    Description,
    Groups,
    Link,
    Recipient,
    Recipients,
    Target,
)
from django_notification.repository.queryset.notification import NotificationQuerySet
from django_notification.utils.user_model import UserModel


# pylint: disable=too-many-arguments
class NotificationDataAccessLayer(Manager):
    """Data Access Layer (DAL) for managing notifications in the application.

    This class provides various methods for creating, updating, deleting, and
    filtering notifications, allowing the management of notification records
    based on different criteria such as recipients, groups, status, and visibility.

    Methods:
        get_queryset: Returns the base notification queryset.
        create_notification: Creates a new notification with specific details.
        update_notification: Updates selective fields of an existing notification.
        delete_notification: Deletes or soft-deletes a notification.
        sent: Retrieves all sent notifications with optional filters.
        unsent: Retrieves all unsent notifications with optional filters.
        seen: Retrieves all notifications seen by a given user.
        unseen: Retrieves all notifications not seen by a given user.
        mark_all_as_sent: Marks all unsent notifications as sent.
        mark_all_as_seen: Marks all unseen notifications for a user as seen.
        deleted: Retrieves all deleted notifications, optionally filtered by user.
        clear_all: Clears all seen notifications for a given user, marking them as deleted.

    """

    def get_queryset(self) -> NotificationQuerySet:
        """Retrieve the base notification queryset for further querying or
        filtering.

        Returns:
            NotificationQuerySet: The base queryset containing all notifications.

        """
        return NotificationQuerySet(model=self.model, using=self._db)

    def create_notification(
        self,
        verb: str,
        actor: Actor,
        description: Optional[Description] = None,
        recipients: Optional[Recipients] = None,
        groups: Optional[Groups] = None,
        status: str = "INFO",
        public: bool = True,
        target: Optional[Target] = None,
        action_object: Optional[ActionObject] = None,
        link: Optional[Link] = None,
        is_sent: bool = False,
        data: Optional[Data] = None,
    ) -> "Notification":
        """Create a new notification with the provided details.

        Args:
            verb (str): A short phrase describing the notification action (e.g., "commented on").
            actor (Actor): The user or entity performing the action.
            description (Optional[Description]): Additional details or context for the notification.
            recipients (Optional[Recipients]): A list of users who will receive the notification.
            groups (Optional[Groups]): A list of groups to target for the notification.
            status (str): The status of the notification (e.g., "INFO", "WARNING"). Defaults to "INFO".
            public (bool): Whether the notification is publicly visible. Defaults to True.
            target (Optional[Target]): The object being acted upon, if applicable.
            action_object (Optional[ActionObject]): The object performing the action, if relevant.
            link (Optional[Link]): A URL associated with the notification.
            is_sent (bool): Whether the notification is marked as sent. Defaults to False.
            data (Optional[Data]): Any additional data related to the notification.

        Returns:
            Notification: The created notification instance.

        """
        notification = self.get_queryset().create_notification(
            verb=verb,
            actor=actor,
            description=description,
            status=status,
            target=target,
            action_object=action_object,
            link=link,
            public=public,
            is_sent=is_sent,
            data=data,
        )

        if recipients:
            if isinstance(recipients, UserModel):
                recipients = [recipients]
            notification.recipient.add(*recipients)

        if groups:
            if isinstance(groups, Group):
                groups = [groups]
            notification.group.add(*groups)

        return notification

    def update_notification(
        self,
        notification_id: int,
        is_sent: Optional[bool] = None,
        public: Optional[bool] = None,
        data: Optional[Data] = None,
    ) -> "Notification":
        """Update specified fields of an existing notification.

        Args:
            notification_id (int): The ID of the notification to be updated.
            is_sent (Optional[bool]): The sent status to update.
            public (Optional[bool]): The public visibility to update.
            data (Optional[Data]): Any additional data to update for the notification.

        Returns:
            Notification: The updated notification instance.

        """
        return self.get_queryset().update_notification(
            notification_id, is_sent, public, data
        )

    def delete_notification(
        self,
        notification_id: int,
        recipient: Optional[Recipient] = None,
        soft_delete: bool = True,
    ) -> None:
        """Delete or soft-delete a notification based on the provided ID.

        Args:
            notification_id (int): The ID of the notification to delete.
            recipient (Optional[Recipient]): The user performing the soft delete. Required for soft deletes.
            soft_delete (bool): Whether to perform a soft delete. Defaults to True.

        Raises:
            ValueError: If `recipient` is not provided for soft delete.

        """
        self.get_queryset().delete_notification(notification_id, recipient, soft_delete)

    def all_notifications(
        self,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
    ) -> QuerySet:
        """Return all notifications excluding those that have been deleted.

        This method retrieves all notifications and excludes those that have
        corresponding entries in the DeletedNotification table, indicating that
        they have been deleted.

        Args:
            recipients (User, optional): The recipients of the notifications. Defaults to None.
            groups (Group, optional): The groups of the notifications. Defaults to None.
            display_detail (bool, optional): Whether the queryset will be displayed with all fields. Defaults to False.

        Returns:
            QuerySet: All notifications that have not been deleted.

        """
        return self.get_queryset().all_notifications(recipients, groups, display_detail)

    def sent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all sent notifications, optionally filtered by recipients,
        groups, and conditions.

        Args:
            recipients (Optional[Recipients]): The intended recipients of the notifications.
            exclude_deleted_by (Optional[Recipient]): Exclude notifications deleted by this user.
            groups (Optional[Groups]): Filter notifications by group.
            display_detail (bool): Whether to display detailed notification fields. Defaults to False.
            conditions (Q): Additional query conditions to filter the queryset. Defaults to an empty Q().

        Returns:
            QuerySet: A queryset of sent notifications.

        """
        return self.get_queryset().sent(
            recipients, exclude_deleted_by, groups, display_detail, conditions
        )

    def unsent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all unsent notifications, with optional filtering.

        Args:
            recipients (Optional[Recipients]): The intended recipients of the notifications.
            exclude_deleted_by (Optional[Recipient]): Exclude notifications deleted by this user.
            groups (Optional[Groups]): Filter notifications by group.
            display_detail (bool): Whether to display detailed notification fields. Defaults to False.
            conditions (Q): Additional query conditions to filter the queryset. Defaults to an empty Q().

        Returns:
            QuerySet: A queryset of unsent notifications.

        """
        return self.get_queryset().unsent(
            recipients, exclude_deleted_by, groups, display_detail, conditions
        )

    def seen(
        self,
        seen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all notifications that have been seen by the given user.

        Args:
            seen_by (UserModel): The user who has seen the notifications.
            recipients (Optional[Recipients]): Filter by recipients, if provided.
            groups (Optional[Groups]): Filter by groups, if provided.
            display_detail (bool): Whether to display detailed fields for each notification.
            conditions (Q): Additional query conditions to filter the queryset.

        Returns:
            QuerySet: A queryset of notifications seen by the user.

        """
        return self.get_queryset().seen(
            seen_by, recipients, groups, display_detail, conditions
        )

    def unseen(
        self,
        unseen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all notifications that have not been seen by the given
        user.

        Args:
            unseen_by (UserModel): The user who has not seen the notifications.
            recipients (Optional[Recipients]): Filter by recipients, if provided.
            groups (Optional[Groups]): Filter by groups, if provided.
            display_detail (bool): Whether to display detailed fields for each notification.
            conditions (Q): Additional query conditions to filter the queryset.

        Returns:
            QuerySet: A queryset of unseen notifications for the user.

        """
        return self.get_queryset().unseen(
            unseen_by, recipients, groups, display_detail, conditions
        )

    def mark_all_as_sent(
        self, recipients: Optional[Recipients] = None, groups: Optional[Groups] = None
    ) -> int:
        """Mark all unsent notifications as sent.

        Args:
            recipients (Optional[Recipients]): Recipients to filter unsent notifications.
            groups (Optional[Groups]): Groups to filter unsent notifications.

        Returns:
            int: The number of notifications marked as sent.

        """
        return self.get_queryset().mark_all_as_sent(recipients, groups)

    def mark_all_as_seen(self, user: UserModel) -> int:
        """Mark all unseen notifications for a user as seen.

        Args:
            user (UserModel): The user to mark notifications as seen for.

        Returns:
            int: The number of notifications marked as seen.

        """
        return self.get_queryset().mark_all_as_seen(user)

    def deleted(self, deleted_by: Recipient = None) -> QuerySet:
        """Retrieve all notifications that have been deleted, optionally
        filtered by user.

        Args:
            deleted_by (Optional[Recipient]): The user to filter deleted notifications by.

        Returns:
            QuerySet: A queryset of deleted notifications.

        """
        return self.get_queryset().deleted(deleted_by)

    def clear_all(self, user: UserModel) -> None:
        """Move notifications to a 'deleted' state for the given recipient.

        This method finds all notifications marked as seen by the recipient
        and creates corresponding entries in the DeletedNotification table
        to indicate that these notifications have been deleted.

        Arguments:
        user (User): The user for whom notifications should be cleared.

        Returns:
        None

        """
        self.get_queryset().clear_all(user)
