from typing import List, Any
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.request import Request


class DisableMethodsMixin:
    """
    A mixin to dynamically disable specified HTTP methods based on configuration or conditions.

    This mixin allows you to disable HTTP methods such as GET, POST, PUT, DELETE, etc.,
    by overriding them with a method that raises `MethodNotAllowed`. This is useful for
    restricting access to certain actions or endpoints based on specific conditions or settings.
    """

    def disable_methods(self, methods: List[str]) -> None:
        """
        Disables the specified HTTP methods by overriding them with a method that raises `MethodNotAllowed`.

        Args:
            methods (List[str]): A list of HTTP method names to disable (e.g., ["GET", "POST"]).

        Example:
            To disable the GET and POST methods:
            ```python
            self.disable_methods(["GET", "POST"])
            ```
        """
        for method in methods:
            method_lower = method.lower()
            if hasattr(self, method_lower):
                setattr(self, method_lower, self._method_not_allowed)

    def _method_not_allowed(self, request: Request, *args: Any, **kwargs: Any) -> None:
        """
        Raises `MethodNotAllowed` for disabled methods.

        Args:
            request (Request): The HTTP request object.
            *args (Any): Additional positional arguments.
            **kwargs (Any): Additional keyword arguments.


        Raises:
            MethodNotAllowed: Indicates that the method is not allowed.
        """
        method = request.method.upper()
        raise MethodNotAllowed(
            method,
            detail=f'The method "{method}" is currently disabled for this endpoint. It can be changed in the settings.',
        )
