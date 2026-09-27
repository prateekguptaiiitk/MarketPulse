"""Alpha Vantage provider for users with a configured API key."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

import requests
from django.conf import settings

from .base import MarketDataProvider, MarketDataProviderError, OHLCVBar


class AlphaVantageProvider(MarketDataProvider):
    """Fetch daily and intraday series from Alpha Vantage's REST API."""

    endpoint = "https://www.alphavantage.co/query"

    def fetch_historical(
        self, symbol: str, start: datetime, end: Optional[datetime], interval: str
    ) -> List[OHLCVBar]:
        api_key = getattr(settings, "ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            raise MarketDataProviderError("ALPHA_VANTAGE_API_KEY must be set to use Alpha Vantage.")
        if interval == "1d":
            function, series_key = "TIME_SERIES_DAILY", "Time Series (Daily)"
            params = {"function": function, "outputsize": "full"}
        elif interval in ("1m", "5m"):
            function, series_key = "TIME_SERIES_INTRADAY", f"Time Series ({interval[:-1]}min)"
            params = {"function": function, "interval": f"{interval[:-1]}min", "outputsize": "full"}
        else:
            raise MarketDataProviderError(f"Unsupported interval: {interval}")
        params.update({"symbol": symbol, "apikey": api_key})
        try:
            response = requests.get(
                self.endpoint,
                params=params,
                timeout=getattr(settings, "MARKET_DATA_TIMEOUT", 20),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MarketDataProviderError(f"Alpha Vantage request failed for {symbol}: {exc}") from exc
        series = payload.get(series_key)
        if not series:
            reason = payload.get("Note") or payload.get("Error Message") or payload.get("Information") or "no data returned"
            raise MarketDataProviderError(f"Alpha Vantage returned no series for {symbol}: {reason}")

        bars: List[OHLCVBar] = []
        for stamp, values in series.items():
            try:
                fmt = "%Y-%m-%d" if interval == "1d" else "%Y-%m-%d %H:%M:%S"
                timestamp = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
                if timestamp < start or (end is not None and timestamp > end):
                    continue
                bars.append(
                    OHLCVBar(
                        timestamp=timestamp,
                        open=Decimal(values["1. open"]),
                        high=Decimal(values["2. high"]),
                        low=Decimal(values["3. low"]),
                        close=Decimal(values["4. close"]),
                        volume=max(0, int(values["5. volume"])),
                    )
                )
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise MarketDataProviderError(f"Invalid Alpha Vantage row for {symbol}: {exc}") from exc
        return sorted(bars, key=lambda bar: bar.timestamp)
