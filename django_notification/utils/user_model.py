from django.contrib.auth import get_user_model

# Cache the user model and username field
UserModel = get_user_model()
USERNAME_FIELD = UserModel.USERNAME_FIELD
REQUIRED_FIELDS = UserModel.REQUIRED_FIELDS


def get_username(user: UserModel) -> str:
    """Utility function to get a user's username.

    Args:
        user (User): The user object.

    Returns:
        str: The username of the user, or "Unknown" if the field is not available.

    """
    return getattr(user, USERNAME_FIELD, "Unknown")
