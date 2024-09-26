from typing import Tuple

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Manager,
    ManyToManyField,
    Model,
    PositiveIntegerField,
    TextField,
    URLField,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_notification.models.helper.enums.status_choices import NotificationStatus
from django_notification.models.notification_recipient import NotificationRecipient
from django_notification.models.notification_seen import NotificationSeen
from django_notification.models.permissions.notification_permission import (
    NotificationPermission,
)
from django_notification.repository.queryset.notification import NotificationQuerySet


class Notification(Model):
    """A model representing notifications sent to users and groups.

    This model supports associating any type of object with a notification through the use of
    generic foreign keys. It stores notification recipients, groups, status, and related objects
    (actor, target, action_object).

    Attributes:
        recipient (ManyToManyField): Users receiving the notification.
        group (ManyToManyField): Groups receiving the notification.
        verb (CharField): The action verb associated with the notification.
        description (TextField): A description of the notification.
        status (CharField): The current status of the notification.
        actor_content_type (ForeignKey): Content type of the actor initiating the action.
        actor_object_id (PositiveIntegerField): ID of the actor object.
        actor (GenericForeignKey): A generic foreign key to the actor object.
        target_content_type (ForeignKey): Content type of the target object.
        target_object_id (PositiveIntegerField): ID of the target object.
        target (GenericForeignKey): A generic foreign key to the target object.
        action_object_content_type (ForeignKey): Content type of the action object.
        action_object_object_id (PositiveIntegerField): ID of the action object.
        action_object (GenericForeignKey): A generic foreign key to the action object.
        link (URLField): URL associated with the action.
        is_sent (BooleanField): Indicates if the notification has been sent.
        seen_by (ManyToManyField): Users who have seen the notification.
        public (BooleanField): Indicates if the notification is public.
        data (JSONField): Additional metadata or attributes associated with the notification.
        timestamp (DateTimeField): Time when the notification was created.

    """

    recipient = ManyToManyField(
        settings.AUTH_USER_MODEL,
        through=NotificationRecipient,
        verbose_name=_("Recipient"),
        help_text=_("The users who will receive the notification."),
        related_name="notifications",
        blank=True,
    )
    group = ManyToManyField(
        Group,
        verbose_name=_("Group"),
        help_text=_("The groups that will receive the notification."),
        blank=True,
    )
    verb = CharField(
        verbose_name=_("Verb"),
        help_text=_(
            "The action verb associated with the notification, e.g., 'liked', 'commented'."
        ),
        db_comment=_(
            "A short description of the action that triggered the notification (e.g., 'liked', 'commented')."
        ),
        max_length=127,
    )
    description = TextField(
        verbose_name=_("Description"),
        help_text=_("The description of the notification."),
        db_comment=_(
            "A textual description providing more detail about the notification."
        ),
        max_length=512,
        blank=True,
        null=True,
    )
    status = CharField(
        choices=NotificationStatus.choices,
        verbose_name=_("Status"),
        help_text=_("The current status of the notification."),
        db_comment=_(
            "Indicates the notification's current status, such as 'info', 'error', or 'warning'."
        ),
        max_length=15,
        default=NotificationStatus.INFO,
    )
    actor_content_type = ForeignKey(
        ContentType,
        verbose_name=_("Actor ContentType"),
        help_text=_("The content type of the actor object."),
        db_comment=_(
            "The content type of the object representing the actor (i.e., the initiator of the notification)."
        ),
        on_delete=CASCADE,
        related_name="actor_content_type_notifications",
    )
    actor_object_id = PositiveIntegerField(
        verbose_name=_("Actor object ID"),
        help_text=_("The ID of the actor object."),
        db_comment=_(
            "The unique ID of the actor object associated with the notification."
        ),
    )
    actor = GenericForeignKey("actor_content_type", "actor_object_id")
    target_content_type = ForeignKey(
        ContentType,
        verbose_name=_("Target ContentType"),
        help_text=_("The content type of the target object."),
        db_comment=_(
            "The content type of the target object of the notification, if applicable."
        ),
        on_delete=CASCADE,
        related_name="target_content_type_notifications",
        blank=True,
        null=True,
    )
    target_object_id = PositiveIntegerField(
        verbose_name=_("Target object ID"),
        help_text=_("The ID of the target object."),
        db_comment=_(
            "The unique ID of the target object associated with the notification, if applicable."
        ),
        blank=True,
        null=True,
    )
    target = GenericForeignKey("target_content_type", "target_object_id")
    action_object_content_type = ForeignKey(
        ContentType,
        verbose_name=_("Action object ContentType"),
        help_text=_("The content type of the action object."),
        db_comment=_(
            "The content type of the action object that triggered the notification, if applicable."
        ),
        on_delete=CASCADE,
        related_name="action_content_type_notifications",
        blank=True,
        null=True,
    )
    action_object_object_id = PositiveIntegerField(
        verbose_name=_("Action object ID"),
        help_text=_("The ID of the action object."),
        db_comment=_(
            "The unique ID of the action object associated with the notification, if applicable."
        ),
        blank=True,
        null=True,
    )
    action_object = GenericForeignKey(
        "action_object_content_type", "action_object_object_id"
    )
    link = URLField(
        verbose_name=_("Link"),
        help_text=_("A URL associated with the action."),
        db_comment=_(
            "A URL related to the notification or action, for further details or follow-up."
        ),
        blank=True,
        null=True,
    )
    is_sent = BooleanField(
        verbose_name=_("Is sent"),
        help_text=_("indicate whether the notification has been sent."),
        db_comment=_(
            "A boolean flag indicating whether this notification has already been sent to its recipients."
        ),
        default=False,
    )
    seen_by = ManyToManyField(
        settings.AUTH_USER_MODEL,
        through=NotificationSeen,
        verbose_name=_("Seen by"),
        help_text=_("Users who have seen the notification."),
    )
    public = BooleanField(
        verbose_name=_("Public"),
        help_text=_("Indicate whether the notification is public."),
        db_comment=_(
            "A boolean flag indicating if this notification is public or private."
        ),
        default=True,
    )
    data = JSONField(
        verbose_name=_("data"),
        help_text=_("Additional metadata or custom attributes in JSON format."),
        db_comment=_(
            "Stores arbitrary JSON data related to the notification, such as custom attributes or metadata."
        ),
        blank=True,
        null=True,
    )
    timestamp = DateTimeField(
        verbose_name=_("Timestamp"),
        help_text=_("The time when the notification was created."),
        db_comment=_("The date and time when this notification was created."),
        default=timezone.now,
        db_index=True,
    )
    objects = Manager()
    queryset = NotificationQuerySet.as_manager()

    class Meta:
        db_table: str = "notification"
        verbose_name: str = _("Notification")
        verbose_name_plural: str = _("Notifications")
        ordering: Tuple[str] = ("-timestamp",)

    def __str__(self) -> str:
        """Return a string representation of the notification including its
        description and the natural time since its timestamp.

        Returns:
            str: The string representation of the notification.

        """
        return f"{self.description} {naturaltime(self.timestamp)}"

    def _title_generator(self) -> str:
        """Generate the title for the notification based on its attributes.

        Returns:
            str: The generated title for the notification.

        """

        if self.target:
            if self.action_object:
                return _("{actor} {verb} {action_object} on {target}").format(
                    actor=self.actor,
                    verb=self.verb,
                    action_object=self.action_object,
                    target=self.target,
                )
            return _("{actor} {verb} {target}").format(
                actor=self.actor,
                verb=self.verb,
                target=self.target,
            )
        if self.action_object:
            return _("{actor} {verb} {action_object}").format(
                actor=self.actor,
                verb=self.verb,
                action_object=self.action_object,
            )
        return _("{actor} {verb}").format(
            actor=self.actor,
            verb=self.verb,
        )

    def mark_as_seen(self, user: settings.AUTH_USER_MODEL) -> None:
        """Mark the notification as seen by a specific user.

        Args:
            user (User): The user who has seen the notification.

        Raises:
            PermissionError: If the user does not have permission to mark the notification as seen.

        """
        permission_class = NotificationPermission(self)
        permission_class.validate_permission(user, "mark as seen")
        self.seen_by.add(user)

    def save(self, *args, **kwargs) -> None:
        """Save the notification instance, automatically generating the
        description if it is not provided.

        Args:
            *args: Additional arguments for the save method.
            **kwargs: Additional keyword arguments for the save method.

        """
        if not self.pk and not self.description:
            self.description = self._title_generator()
        super().save(*args, **kwargs)
