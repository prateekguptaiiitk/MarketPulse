"""Factory Boy fixtures for strategy evaluation tests."""
import factory

from accounts.factories import UserFactory
from strategies.models import Strategy


class StrategyFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda number: f"Strategy {number}")
    rules = [{"indicator": "RSI", "condition": "less_than", "value": 30}]
    logic = Strategy.Logic.AND
    exit_rules = [{"indicator": "RSI", "condition": "greater_than", "value": 60}]
    exit_logic = Strategy.Logic.OR
    is_active = True

    class Meta:
        model = Strategy
