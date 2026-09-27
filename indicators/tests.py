"""Known-value calculation and endpoint tests using deterministic price data."""
from datetime import datetime, timedelta, timezone

import pandas as pd
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from instruments.models import Instrument, PriceBar
from indicators.services import calculate_indicator


def price_frame(closes, volumes=None):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return pd.DataFrame(
        {"close": closes, "volume": volumes or [100] * len(closes)},
        index=[start + timedelta(days=offset) for offset in range(len(closes))],
    )


class IndicatorCalculationTests(TestCase):
    def test_sma_ema_and_bollinger_band_known_values(self):
        frame = price_frame([2, 4, 6])
        sma = calculate_indicator(frame, "sma", {"period": 2})["series"]["sma"]
        self.assertIsNone(sma[0]["value"])
        self.assertEqual(sma[1]["value"], 3.0)
        self.assertEqual(sma[2]["value"], 5.0)

        ema = calculate_indicator(frame, "ema", {"period": 2})["series"]["ema"]
        self.assertIsNone(ema[0]["value"])
        self.assertAlmostEqual(ema[1]["value"], 3.3333333333333335)
        self.assertAlmostEqual(ema[2]["value"], 5.111111111111111)

        bands = calculate_indicator(frame, "bollinger", {"period": 2, "stddev": 2})["series"]
        self.assertEqual(bands["middle"][2]["value"], 5.0)
        self.assertAlmostEqual(bands["upper"][2]["value"], 7.0)
        self.assertAlmostEqual(bands["lower"][2]["value"], 3.0)

    def test_rsi_macd_and_volume_spike(self):
        rsi = calculate_indicator(price_frame([1, 2, 3, 2, 2]), "rsi", {"period": 2})["series"]["rsi"]
        self.assertIsNone(rsi[1]["value"])
        self.assertEqual(rsi[2]["value"], 100.0)
        self.assertEqual(rsi[3]["value"], 50.0)
        self.assertEqual(rsi[4]["value"], 50.0)

        macd = calculate_indicator(price_frame(list(range(1, 31))), "macd", {"fast": 2, "slow": 4, "signal": 2})["series"]
        self.assertIsNone(macd["macd"][2]["value"])
        self.assertIsNotNone(macd["histogram"][-1]["value"])

        volume = calculate_indicator(price_frame([10, 11, 12], [10, 10, 100]), "volume_spike", {"period": 2, "threshold": 2})["series"]
        self.assertIsNone(volume["ratio"][1]["value"])
        self.assertEqual(volume["ratio"][2]["value"], 10.0)
        self.assertTrue(volume["spike"][2]["value"])

    def test_invalid_indicator_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_indicator(price_frame([1, 2]), "sma", {"period": 0})
        with self.assertRaises(ValueError):
            calculate_indicator(price_frame([1, 2]), "macd", {"fast": 5, "slow": 5})


class IndicatorEndpointTests(TestCase):
    def test_indicator_endpoint_returns_aligned_series_and_validates_query(self):
        user = User.objects.create_user("indicator@example.com", "Strong-example-pass-734!")
        instrument = Instrument.objects.create(symbol="IND", name="Indicator Equity")
        for index, close in enumerate((10, 12, 14)):
            PriceBar.objects.create(
                instrument=instrument,
                timestamp=datetime(2025, 1, index + 1, tzinfo=timezone.utc),
                open=close, high=close, low=close, close=close, volume=100,
            )
        client = APIClient()
        client.force_authenticate(user)

        response = client.get(f"/api/v1/instruments/{instrument.pk}/indicators/?indicators=sma&lookback=3&period=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["indicators"]["sma"]["series"]["sma"][-1]["value"], 13.0)
        invalid = client.get(f"/api/v1/instruments/{instrument.pk}/indicators/?indicators=nope")
        self.assertEqual(invalid.status_code, 400)
