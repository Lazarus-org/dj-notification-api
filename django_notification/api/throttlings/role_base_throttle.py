from rest_framework.request import Request
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView


class RoleBasedUserRateThrottle(UserRateThrottle):
    """A custom throttle class that limits the rate of requests based on the
    user's role.

    This throttle applies different rates for authenticated users and staff users:

    - Regular authenticated users are limited to the rate defined in the configuration
      (e.g., 30 requests per minute).
    - Staff users (users with the 'is_staff' attribute set to True) are allowed a higher
      rate, also defined in the configuration (e.g., 100 requests per minute).

    The rate limits are retrieved from the project's settings, allowing easy
    configuration adjustments without modifying the code.

    """

    def get_rate(self) -> str:
        """Retrieve the throttle rate based on the user's role.

        This method overrides the default `get_rate` implementation to provide a
        dynamic rate based on the user's role:

        - Regular authenticated users are assigned the rate defined in the
          `authenticated_user_throttle_rate` setting.
        - Staff users (those with `is_staff=True`) are assigned the rate defined in the
          `staff_user_throttle_rate` setting.

        Note:
            This method sets the base rate as the default for regular authenticated
            users. Staff users will have their rate applied in the `allow_request`
            method.

        Returns:
            str: The throttle rate for regular authenticated users, as defined in the
                 project settings.

        """
        from django_notification.settings.conf import config

        # Set throttle rates from configuration
        self.base_rate: str = config.authenticated_user_throttle_rate
        self.staff_rate: str = config.staff_user_throttle_rate

        return self.base_rate

    def allow_request(self, request: Request, view: APIView) -> bool:
        """Determine whether the current request is allowed based on the user's
        role and the configured throttle rates.

        - If the user is a staff member (`is_staff=True`), the throttle rate is set
          to the staff rate from the project configuration.
        - Otherwise, the regular authenticated user throttle rate is used.

        Unauthenticated (anonymous) users are not allowed to proceed if this throttle is applied.

        Args:
            request (Request): The incoming HTTP request object, which contains user information.
            view (APIView): The API view being accessed by the request.

        Returns:
            bool: True if the request is allowed based on the user's rate limit; False otherwise.

        """
        user = request.user

        # Apply staff rate for staff users
        if user.is_staff:
            self.rate = self.staff_rate

        # Parse rate to get number of requests and duration
        self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)
