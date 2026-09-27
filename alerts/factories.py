"""Factory Boy fixtures for alert API and notification tests."""
import factory

from accounts.factories import UserFactory
from instruments.factories import InstrumentFactory
from alerts.models import Alert


class AlertFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    instrument = factory.SubFactory(InstrumentFactory)
    name = factory.Sequence(lambda number: f"Alert {number}")
    condition = {"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 100}]}
    notification_channel = Alert.NotificationChannel.EMAIL
    cooldown_minutes = 5

    class Meta:
        model = Alert
