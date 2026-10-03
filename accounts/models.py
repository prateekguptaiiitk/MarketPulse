"""Custom email-authenticated user model."""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from typing import Optional

'''
    Custom manager for storing built-in user model in a customized way
'''
class UserManager(BaseUserManager):
    """Create users with normalized email addresses."""

    use_in_migrations = True

    def create_user(self, email: str, password: Optional[str] = None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)    # normalizing means lowercasing, trimming spaces and handling aliases like john+news@gmail.com and john@gmail.com
        user.set_password(password)
        user.save(using=self._db)   # self._db points to 'default' db mentioned in settings.py
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superusers must have staff and superuser status.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()     # for adding custom manager and not using standard built-in user model manager
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email
