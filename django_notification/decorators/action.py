from functools import wraps
from typing import Any, Callable

from rest_framework.decorators import action


def conditional_action(condition: bool, *args: Any, **kwargs: Any) -> Callable:
    """Conditionally apply the Django REST Framework's `action` decorator based
    on the given condition.

    Args:
        condition (bool): A boolean condition to determine if the `action` decorator should be applied.
        *args: Positional arguments to pass to the `action` decorator if applied.
        **kwargs: Keyword arguments to pass to the `action` decorator if applied.

    Returns:
        Callable: The decorated function if the condition is true, otherwise the original function.

    Raises:
        TypeError: If `condition` is not a boolean.

    """
    if not isinstance(condition, bool):
        raise TypeError("The 'condition' argument must be of type bool.")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapped_func(*f_args: Any, **f_kwargs: Any) -> Any:
            return func(*f_args, **f_kwargs)

        if condition:
            return action(*args, **kwargs)(wrapped_func)

        return wrapped_func

    return decorator
