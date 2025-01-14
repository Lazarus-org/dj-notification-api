import sys

import pytest
from rest_framework.response import Response

from django_notification.decorators.action import conditional_action
from django_notification.tests.constants import PYTHON_VERSION, PYTHON_VERSION_REASON

pytestmark = [
    pytest.mark.decorators,
    pytest.mark.decorators_action,
    pytest.mark.skipif(sys.version_info < PYTHON_VERSION, reason=PYTHON_VERSION_REASON),
]


@pytest.mark.django_db
class TestConditionalAction:
    """
    Test suite for the `conditional_action` decorator.
    """

    def test_action_with_invalid_type(self) -> None:
        """
        Test that the `conditional_action` decorator raises a TypeError when the type of the condition is not bool.

        Asserts:
        -------
            - A TypeError is raised when the condition provided is not of type bool.
        """
        with pytest.raises(TypeError):

            @conditional_action("True", detail=False, methods=["get"])  # type: ignore
            def action_with_condition_true() -> Response:
                return Response({"message": "Action with condition True"})

    def test_action_with_false_condition(self) -> None:
        """
        Test that the action function is not decorated with the DRF @action when condition=False.

        Asserts:
        -------
            - The function behaves like a regular function and does not register as a DRF action.
        """

        @conditional_action(condition=False, detail=False, methods=["get"])
        def false_action() -> str:
            """
            Action that should not be registered as a DRF action because condition=False.
            """
            return "This is a regular function, not an action."

        # Ensure that the function behaves like a normal function, not an API action
        result = false_action()
        assert result == "This is a regular function, not an action."
