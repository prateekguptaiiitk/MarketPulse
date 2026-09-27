"""Factory Boy fixture for persistent backtest job tests."""
from decimal import Decimal

import factory

from accounts.factories import UserFactory
from backtesting.models import BacktestRun
from instruments.factories import InstrumentFactory
from strategies.factories import StrategyFactory


class BacktestRunFactory(factory.django.DjangoModelFactory):
    requested_by = factory.SubFactory(UserFactory)
    strategy = factory.SubFactory(StrategyFactory, user=factory.SelfAttribute("..requested_by"))
    instrument = factory.SubFactory(InstrumentFactory)
    date_range = {"start": "2025-01-01", "end": "2025-01-31"}
    initial_capital = Decimal("10000.00")

    class Meta:
        model = BacktestRun
