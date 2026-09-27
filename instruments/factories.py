"""Factory Boy fixtures for instrument and bar tests."""
from decimal import Decimal

import factory
from django.utils import timezone

from instruments.models import Instrument, PriceBar


class InstrumentFactory(factory.django.DjangoModelFactory):
    symbol = factory.Sequence(lambda number: f"TEST{number}")
    name = factory.LazyAttribute(lambda instrument: f"{instrument.symbol} Corporation")
    exchange = "NASDAQ"
    sector = "Technology"
    is_active = True

    class Meta:
        model = Instrument


class PriceBarFactory(factory.django.DjangoModelFactory):
    instrument = factory.SubFactory(InstrumentFactory)
    timestamp = factory.LazyFunction(timezone.now)
    open = Decimal("100.00")
    high = Decimal("102.00")
    low = Decimal("99.00")
    close = Decimal("101.00")
    volume = 100_000
    interval = PriceBar.Interval.ONE_DAY

    class Meta:
        model = PriceBar
