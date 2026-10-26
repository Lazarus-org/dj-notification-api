"""Exercise swapped users both with and without Django auth groups."""

from django.contrib.auth.models import AbstractBaseUser, AbstractUser, BaseUserManager
from django.db import models


class CustomUser(AbstractUser):
    pass


class BareUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = BaseUserManager()
