from typing import Dict, List, Optional, Union

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Model, Q, QuerySet, Subquery
from rest_framework.generics import get_object_or_404

from django_notification.constants.qs_types import (
    ActionObject,
    Actor,
    Data,
    Description,
    Groups,
    Link,
    OptConditions,
    Recipient,
    Recipients,
    Target,
)
from django_notification.models.deleted_notification import DeletedNotification
from django_notification.models.notification_seen import NotificationSeen
from django_notification.utils.user_model import UserModel


# pylint: disable=too-many-arguments
class NotificationQuerySet(QuerySet):
    def with_related(self) -> QuerySet:
        """Prefetch related fields for notifications."""
        return self.prefetch_related(
            "recipient", "group", "group__permissions", "seen_by"
        )

    def _get_deleted_notifications(self, deleted_by: Recipient = None) -> QuerySet:
        """Retrieve deleted notifications optionally filtered by user who
        delete the notification."""
        queryset = DeletedNotification.objects.values("notification")
        if deleted_by:
            queryset = queryset.filter(user=deleted_by)
        return queryset

    def _get_notifications_queryset(
        self,
        exclude_deleted_by: Recipient = None,
        display_detail: bool = False,
        conditions: OptConditions = None,
    ) -> Union[QuerySet, Dict]:
        """Return a queryset of notifications based on the given conditions.

        This method retrieves a queryset of notifications based on the given conditions
        and excludes those that have corresponding entries in the DeletedNotification table,
        indicating that they have been deleted.

        Args:
            display_detail (bool, optional): Whether the queryset will be displayed with all fields. Defaults to False.
            conditions (Q, optional): The query conditions to apply to the queryset. Defaults to None.

        Returns:
            QuerySet: A queryset of notifications that match the given conditions.

        """
        queryset = self.with_related()

        if exclude_deleted_by:
            deleted_notifications = self._get_deleted_notifications(
                deleted_by=exclude_deleted_by
            )
            queryset = self.with_related().exclude(
                id__in=Subquery(deleted_notifications)
            )

        if conditions:
            queryset = queryset.filter(conditions)
        if not display_detail:
            queryset = queryset.values(
                "id", "description", "status", "link", "timestamp"
            )

        return queryset

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

        conditions = Q()
        if recipients:
            if isinstance(recipients, UserModel):
                recipients = [recipients]
            conditions = Q(recipient__in=recipients)
        if groups:
            if isinstance(groups, Group):
                groups = [groups]
            conditions &= Q(group__in=groups)
        return self._get_notifications_queryset(
            display_detail=display_detail, conditions=conditions
        )

    def sent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Return all sent notifications.

        Args:
            recipients (User, optional): The recipients of the notifications. Defaults to None.
            exclude_deleted_by (User, Optional): The user that the deleted notifications will be excluded for.
             Defaults to None.
            groups (Group, optional): The groups of the notifications. Defaults to None.
            display_detail (bool, optional): Whether the queryset will be displayed with sll fields. Defaults to False.
            conditions (Q, optional): The query conditions to apply to the queryset. Defaults empty Q().

        Returns:
            QuerySet: All sent notifications.

        """
        conditions &= Q(is_sent=True)
        or_conditions = Q()

        if recipients:
            if isinstance(recipients, UserModel):
                recipients = [recipients]
            or_conditions = Q(recipient__in=recipients)
        elif exclude_deleted_by and not (
            exclude_deleted_by.is_staff or exclude_deleted_by.is_superuser
        ):
            or_conditions |= Q(recipient=exclude_deleted_by)

        if groups:
            if isinstance(groups, Group):
                groups = [groups]
            or_conditions |= Q(group__in=groups)

        conditions &= or_conditions

        return self._get_notifications_queryset(
            exclude_deleted_by=exclude_deleted_by,
            display_detail=display_detail,
            conditions=conditions,
        )

    def unsent(
        self,
        recipients: Recipients = None,
        exclude_deleted_by: Recipient = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Return all unsent notifications.

        Args:
            recipients (User, optional): The recipient of the notifications. Defaults to None.
            exclude_deleted_by (User, Optional): The user that the deleted notifications will be excluded for.
             Defaults to None.
            groups (Group, optional): The groups of the notifications. Defaults to None.
            display_detail (bool, optional): Whether the queryset will be displayed with all fields. Defaults to False.
            conditions (Q, optional): The query conditions to apply to the queryset. Defaults empty Q().

        Returns:
            QuerySet: All unsent notifications.

        """
        conditions &= Q(is_sent=False)
        or_conditions = Q()

        if recipients:
            if isinstance(recipients, UserModel):
                recipients = [recipients]
            or_conditions = Q(recipient__in=recipients)
        elif exclude_deleted_by and not (
            exclude_deleted_by.is_staff or exclude_deleted_by.is_superuser
        ):
            or_conditions |= Q(recipient=exclude_deleted_by)

        if groups:
            if isinstance(groups, Group):
                groups = [groups]
            or_conditions |= Q(group__in=groups)

        conditions &= or_conditions
        return self._get_notifications_queryset(
            exclude_deleted_by=exclude_deleted_by,
            display_detail=display_detail,
            conditions=conditions,
        )

    def seen(
        self,
        seen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all notifications that have been seen by the specified
        user.

        This method filters notifications that have been marked as "seen" by the provided user (`seen_by`). It also supports additional filtering based on recipients, groups, and custom conditions. The method ensures that only sent notifications are retrieved, excluding any that the user has deleted.

        Args:
            seen_by (UserModel): The user who has seen the notifications.
            recipients (Optional[Recipients]): Optional filter for the intended recipients of the notifications. Can be a single recipient or multiple.
            groups (Optional[Groups]): Optional filter for group-based notifications. Can be a single group or multiple.
            display_detail (bool): If `True`, include detailed information about each notification. Defaults to `False`.
            conditions (Q): Optional additional query conditions to filter the notifications. Defaults to an empty Q() condition.

        Returns:
            QuerySet: A queryset of sent notifications that have been seen by the specified user, filtered by recipients and groups if provided.

        """
        conditions &= Q(seen_by=seen_by)
        return self.sent(
            recipients=recipients,
            exclude_deleted_by=seen_by,
            groups=groups,
            display_detail=display_detail,
            conditions=conditions,
        )

    def unseen(
        self,
        unseen_by: UserModel,
        recipients: Recipients = None,
        groups: Groups = None,
        display_detail: bool = False,
        conditions: Q = Q(),
    ) -> QuerySet:
        """Retrieve all notifications that have not been seen by the specified
        user.

        This method returns notifications that have been sent but not yet marked as "seen" by the provided user (`unseen_by`). It also supports filtering by recipients, groups, and additional query conditions. Any notifications that have been deleted by the user are excluded from the result.

        Args:
            unseen_by (UserModel): The user who has not seen the notifications.
            recipients (Optional[Recipients]): Optional filter for the intended recipients of the notifications. Can be a single recipient or multiple.
            groups (Optional[Groups]): Optional filter for group-based notifications. Can be a single group or multiple.
            display_detail (bool): If `True`, include detailed information about each notification. Defaults to `False`.
            conditions (Q): Optional additional query conditions to filter the notifications. Defaults to an empty Q() condition.

        Returns:
            QuerySet: A queryset of sent notifications that the specified user has not yet seen, filtered by recipients and groups if provided.

        """
        return self.sent(
            recipients=recipients,
            exclude_deleted_by=unseen_by,
            groups=groups,
            display_detail=display_detail,
            conditions=conditions,
        ).exclude(seen_by=unseen_by)

    @transaction.atomic
    def mark_all_as_seen(self, user: UserModel) -> int:
        """Mark all notifications as seen by the given user that is a recipient
        or a group member.

        Args:
            user(User): The user to mark notifications as seen for.

        Returns:
            The number of notifications marked as seen.

        """

        notifications = self.unseen(unseen_by=user, display_detail=True)
        notifications_to_mark = [
            NotificationSeen(notification=notification, user=user)
            for notification in notifications
        ]
        NotificationSeen.objects.bulk_create(notifications_to_mark)
        return notifications.count()

    def mark_all_as_sent(
        self,
        recipients: Recipients = None,
        groups: Groups = None,
    ) -> int:
        """Mark notifications as sent.

        Args:
            recipients: Filter notifications by recipients.
            groups: Filter notifications by groups.

        Returns:
            The number of notifications marked as sent.

        """
        return self.unsent(
            recipients=recipients, groups=groups, display_detail=True
        ).update(is_sent=True)

    def deleted(self, deleted_by: Recipient = None) -> QuerySet:
        """Retrieve all notifications that have been deleted, optionally
        filtered by user.

        Args:
            deleted_by (Optional[Recipient]): The user to filter deleted notifications by.

        Returns:
            QuerySet: A queryset of deleted notifications.

        """

        deleted_notifications = self._get_deleted_notifications(deleted_by=deleted_by)
        return self.with_related().filter(id__in=Subquery(deleted_notifications))

    @transaction.atomic
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
        # Get notifications seen by the recipient
        notifications = self.seen(seen_by=user, display_detail=True)
        # Create DeletedNotification entries for each sent notification
        deleted_notifications = [
            DeletedNotification(notification=notification, user=user)
            for notification in notifications
        ]
        DeletedNotification.objects.bulk_create(deleted_notifications)

    def create_notification(
        self,
        verb: str,
        actor: Actor,
        description: Description = None,
        status: str = "INFO",
        public: bool = True,
        target: Target = None,
        action_object: ActionObject = None,
        link: Link = None,
        is_sent: bool = False,
        data: Data = None,
    ):
        """Create a new notification.

        Args:
            verb (str): The verb of the notification.
            description (Optional[str]): The description of the notification.
            actor (Model): The actor of the notification.
            status (Optional[str], optional): The status of the notification. Defaults to "INFO".
            target (Optional[Model], optional): The target of the notification. Defaults to None.
            action_object (Optional[Model], optional): The action object of the notification. Defaults to None.
            link (Optional[str], optional): The link of the notification. Defaults to None.
            is_sent (bool, optional): The send status of the notification. Defaults to False.
            public (bool, optional): The public status of the notification. Defaults to True.
            data (Optional[dict], optional): The data of the notification. Defaults to None.

        Returns:
            Notification: The created notification.

        Example:
            queryset.create_notification(
                verb="liked your post",
                description="User liked your post",
                actor=actor,
                recipients=User.objects.filter(is_staff=True),
                groups=Group.objects.filter(name__icontains="Admins"),
                status="INFO",
                public=False,
                target=post,
                link="https://example.com/posts/123",
                is_sent=True,
                data={"custom_data": "value"}
            )

        """

        notification = self.create(
            status=status,
            verb=verb,
            description=description,
            actor=actor,
            target=target,
            action_object=action_object,
            link=link,
            is_sent=is_sent,
            public=public,
            data=data,
        )

        return notification

    def update_notification(
        self,
        notification_id: int,
        is_sent: Optional[bool] = None,
        public: Optional[bool] = None,
        data: Data = None,
    ):
        """Update the status of a notification selectively.

        Args:
            notification_id: The ID of the notification.
            is_sent: The send status of the notification. If None, the field will not be updated.
            public: The public status of the notification. If None, the field will not be updated.
            data: The data of the notification. If None, the field will not be updated.

        Returns:
            The updated notification.

        """
        notification = get_object_or_404(self, pk=notification_id)
        update_fields: List[str] = []

        if is_sent is not None:
            notification.is_sent = is_sent
            update_fields.append("is_sent")
        if public is not None:
            notification.public = public
            update_fields.append("public")
        if data is not None:
            notification.data = data
            update_fields.append("data")

        if update_fields:
            notification.save(update_fields=update_fields)

        return notification

    def delete_notification(
        self,
        notification_id: int,
        recipient: Recipient = None,
        soft_delete: bool = True,
    ) -> None:
        """Delete a notification.

        Args:
            notification_id: The ID of the notification.
            recipient: The recipient of the notification, None as default.
            soft_delete: Indicate the delete level of the notification.

        """
        queryset = self.sent(display_detail=True)
        if recipient:
            queryset = self.sent(exclude_deleted_by=recipient, display_detail=True)
            if not (recipient.is_superuser or recipient.is_staff):
                queryset = self.sent(
                    recipients=recipient,
                    exclude_deleted_by=recipient,
                    display_detail=True,
                )

        instance = get_object_or_404(queryset, pk=notification_id)
        if soft_delete:
            if not recipient:
                raise ValueError("the recipient most be given if it is soft delete")

            DeletedNotification.objects.create(notification=instance, user=recipient)
            return

        instance.delete()
