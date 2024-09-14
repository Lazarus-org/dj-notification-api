from django.conf import settings
import django
import string
import random


def generate_secret_key(length: int = 50) -> str:
    """
    Generates a random secret key for Django settings.

    Args:
        length (int): The length of the secret key. Default is 50 characters.

    Returns:
        str: A randomly generated secret key.
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(random.choice(characters) for _ in range(length))


def configure_django_settings() -> None:
    """
    Configures Django settings for testing or standalone usage.

    This function sets up Django's settings if they are not already configured.
    It configures the following settings:

    - DEBUG: Enables Django's debug mode.
    - SECRET_KEY: Provides a generated secret key for Django settings.
    - DATABASES: Configures an in-memory SQLite database for testing.
    - INSTALLED_APPS: Includes essential Django and third-party apps needed for the test environment.
    - MIDDLEWARE: Configures the middleware stack used by Django.
    - ROOT_URLCONF: Specifies the root URL configuration module.
    - DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE: Enables soft delete functionality in the API.
    - DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE: Enables hard delete functionality in the API.
    - DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION: Disables add permissions for the admin interface.
    - DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION: Disables change permissions for the admin interface.
    - DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION: Disables delete permissions for the admin interface.
    - DJANGO_NOTIFICATION_API_ALLOW_LIST: Allows listing of notifications in the API.
    - DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE: Allows retrieval of notifications in the API.
    - DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE: Sets throttle rate for authenticated users.
    - DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE: Sets throttle rate for staff users.
    - TEMPLATES: Configures the template engine settings.
    - LANGUAGE_CODE: Sets the language code for the application.
    - TIME_ZONE: Sets the time zone for the application.
    - USE_I18N: Enables or disables Django's translation system.
    - USE_TZ: Enables or disables timezone support.
    - STATIC_URL: Specifies the URL for serving static files.

    Side Effects:
    --------------
    - Configures Django settings if they are not already set.
    - Calls `django.setup()` to initialize Django with the configured settings.

    Notes:
    ------
    This function is intended for use in testing environments or standalone scripts where
    a minimal Django setup is required. It does not configure production settings.
    """
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY=generate_secret_key(),  # Add a secret key for testing
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.admin",
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.staticfiles",
                "rest_framework",
                "django_filters",
                "django_notification",
            ],
            MIDDLEWARE=[
                "django.middleware.security.SecurityMiddleware",
                "django.contrib.sessions.middleware.SessionMiddleware",
                "django.middleware.common.CommonMiddleware",
                "django.middleware.csrf.CsrfViewMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
                "django.contrib.messages.middleware.MessageMiddleware",
                "django.middleware.clickjacking.XFrameOptionsMiddleware",
            ],
            ROOT_URLCONF="kernel.urls",
            DJANGO_NOTIFICATION_API_INCLUDE_SOFT_DELETE=True,
            DJANGO_NOTIFICATION_API_INCLUDE_HARD_DELETE=True,
            DJANGO_NOTIFICATION_ADMIN_HAS_ADD_PERMISSION=False,
            DJANGO_NOTIFICATION_ADMIN_HAS_CHANGE_PERMISSION=False,
            DJANGO_NOTIFICATION_ADMIN_HAS_DELETE_PERMISSION=False,
            DJANGO_NOTIFICATION_API_ALLOW_LIST=True,
            DJANGO_NOTIFICATION_API_ALLOW_RETRIEVE=True,
            DJANGO_NOTIFICATION_AUTHENTICATED_USER_THROTTLE_RATE="20/minute",
            DJANGO_NOTIFICATION_STAFF_USER_THROTTLE_RATE="50/minute",
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [],
                    "APP_DIRS": True,
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.debug",
                            "django.template.context_processors.request",
                            "django.contrib.auth.context_processors.auth",
                            "django.contrib.messages.context_processors.messages",
                        ],
                    },
                },
            ],
            LANGUAGE_CODE="en-us",
            TIME_ZONE="UTC",
            USE_I18N=True,
            USE_TZ=True,
            STATIC_URL="static/",
        )
        django.setup()


configure_django_settings()
