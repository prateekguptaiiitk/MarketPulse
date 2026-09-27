"""Factory Boy fixtures for account and authentication tests."""
import factory

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Sequence(lambda number: f"trader-{number}@example.com")
    password = "Factory-user-password-456!"

    class Meta:
        model = User

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", cls.password)
        return model_class.objects.create_user(*args, password=password, **kwargs)
