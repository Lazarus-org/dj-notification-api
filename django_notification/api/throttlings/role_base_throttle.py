from rest_framework.request import Request
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView


class RoleBasedUserRateThrottle(UserRateThrottle):
    """
    A custom throttle class that limits the rate of requests based on the user's role.

    This throttle applies different rates for authenticated users and staff users:

    - Regular authenticated users are limited to the rate defined in the configuration
      (e.g., 30 requests per minute).
    - Staff users (users with the 'is_staff' attribute set to True) are allowed a higher
      rate, also defined in the configuration (e.g., 100 requests per minute).

    The rate limits are retrieved from the project's settings to allow for easy
    configuration adjustments without modifying the code.
    """

    def allow_request(self, request: Request, view: APIView) -> bool:
        """
        Determine whether the current request is allowed based on the user's role and
        the configured throttle rates.

        For authenticated users, the throttle rate is dynamically set based on their role:

        - Regular authenticated users are throttled according to the 'throttle_authenticated_user_rate'
          setting.
        - Staff users are throttled according to the 'staff_user_throttle_rate' setting.

        Unauthenticated (anonymous) users are not allowed to proceed if this throttle is applied.

        Args:
            request (Request): The incoming HTTP request object, which contains user information.
            view (APIView): The API view being accessed by the request.

        Returns:
            bool: True if the request is allowed based on the user's rate limit; False otherwise.
        """
        from django_notification.settings.conf import config

        user = request.user
        if user.is_authenticated:
            self.rate = config.authenticated_user_throttle_rate

            if user.is_staff:
                self.rate = config.staff_user_throttle_rate

            self.num_requests, self.duration = self.parse_rate(self.rate)

        return super().allow_request(request, view)
