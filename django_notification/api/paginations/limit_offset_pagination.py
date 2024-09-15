from typing import Optional

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.request import Request


class DefaultLimitOffSetPagination(LimitOffsetPagination):
    """A custom LimitOffsetPagination class that enforces minimum and maximum
    limits on the number of items returned per page."""

    # Minimum limit allowed in query parameters
    min_limit: int = 1

    # Maximum limit allowed in query parameters
    max_limit: int = 100

    # Default limit when no limit is specified
    default_limit: int = 10

    def get_limit(self, request: Request) -> Optional[int]:
        """Override the `get_limit` method to enforce minimum and maximum
        limits on the number of items returned per page. The limit is extracted
        from the request's query parameters.

        Parameters:
        -----------
        request : Request
            The request object containing query parameters with the pagination limit.

        Returns:
        --------
        Optional[int]
            The number of items to be returned per page, constrained by the defined
            minimum and maximum limits, or the default limit if not specified.

        """
        limit = request.query_params.get(self.limit_query_param)

        if limit:
            try:
                # Try to convert the limit to an integer
                limit = int(limit)

                # Enforce the minimum limit
                if limit < self.min_limit:
                    return self.default_limit

                # Enforce the maximum limit
                if limit > self.max_limit:
                    return self.max_limit

                return limit

            except ValueError:
                # If limit is not a valid integer, fall back to the default limit
                pass

        # Return the default limit if no valid limit is provided
        return self.default_limit
