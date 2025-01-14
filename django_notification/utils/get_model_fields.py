from typing import List, Type

from django.db.models import Model


def get_model_fields(model: Type[Model]) -> List:
    """Get all field names for a given Django model.

    Args:
        model (Model): The Django model class.

    Returns:
        list: A list of all field names in the model.

    """
    return [field.name for field in model._meta.get_fields()]
