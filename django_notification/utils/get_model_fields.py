from typing import List, Type

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import Model
from django.db.models.fields.related import RelatedField


def get_serializable_model_fields(model: Type[Model]) -> List[str]:
    """Get all serializable field names for a given Django model that can be
    passed to the `fields` attribute of a ModelSerializer.

    Args:
        model (Model): The Django model class.

    Returns:
        list: A list of serializable field names in the model.

    """
    serializable_fields = []
    for field in model._meta.get_fields():
        # Exclude reverse relations and auto-created fields
        if (
            field.is_relation
            and field.auto_created
            and not isinstance(field, RelatedField)
        ):
            continue

        # Exclude GenericForeignKey fields
        if isinstance(field, GenericForeignKey):
            continue

        serializable_fields.append(field.name)

    return serializable_fields
