"""Deterministic tests for provider selection and historical backfill."""
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from instruments.models import Instrument, PriceBar
from market_data.providers.base import MarketDataProviderError, OHLCVBar
from market_data.providers.factory import get_market_data_provider


class MarketDataProviderTests(TestCase):
    @override_settings(MARKET_DATA_PROVIDER="alpha_vantage")
    def test_factory_selects_provider_from_settings(self):
        self.assertEqual(get_market_data_provider().__class__.__name__, "AlphaVantageProvider")

    @override_settings(MARKET_DATA_PROVIDER="unknown")
    def test_unknown_provider_fails_with_clear_error(self):
        with self.assertRaises(MarketDataProviderError):
            get_market_data_provider()

    @patch("instruments.management.commands.backfill_history.get_market_data_provider")
    def test_backfill_upserts_mocked_provider_bars_idempotently(self, get_provider):
        instrument = Instrument.objects.create(symbol="MOCK", name="Mock Equity")
        bar = OHLCVBar(
            timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
            open=Decimal("10"), high=Decimal("12"), low=Decimal("9"), close=Decimal("11"), volume=100,
        )
        provider = get_provider.return_value
        provider.fetch_historical.return_value = [bar]
        output = StringIO()

        call_command("backfill_history", symbols=[instrument.symbol], start="2025-01-01", stdout=output)
        call_command("backfill_history", symbols=[instrument.symbol], start="2025-01-01", stdout=output)

        self.assertEqual(PriceBar.objects.filter(instrument=instrument).count(), 1)
        self.assertEqual(PriceBar.objects.get(instrument=instrument).close, Decimal("11.000000"))
        self.assertEqual(provider.fetch_historical.call_count, 2)

    @patch("instruments.management.commands.backfill_history.get_market_data_provider")
    def test_backfill_rejects_invalid_ohlc_rows_without_persisting(self, get_provider):
        instrument = Instrument.objects.create(symbol="MOCK", name="Mock Equity")
        provider = get_provider.return_value
        provider.fetch_historical.return_value = [
            OHLCVBar(datetime(2025, 1, 2, tzinfo=timezone.utc), Decimal("10"), Decimal("8"), Decimal("9"), Decimal("11"), 100)
        ]

        with self.assertRaises(CommandError):
            call_command("backfill_history", symbols=[instrument.symbol], start="2025-01-01")
        self.assertFalse(PriceBar.objects.filter(instrument=instrument).exists())
