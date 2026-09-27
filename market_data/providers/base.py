"""Provider contract and normalized market bar value object."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from datetime import timedelta
from typing import List, Optional


@dataclass(frozen=True)
class OHLCVBar:
    """A provider-neutral OHLCV bar with a timezone-aware timestamp."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class MarketDataProviderError(Exception):
    """Raised when a market data provider cannot return usable data."""


def validate_ohlcv_bar(bar: "OHLCVBar", symbol: str = "instrument") -> None:
    """Ensure a normalized bar has finite, internally consistent OHLCV data."""
    prices = (bar.open, bar.high, bar.low, bar.close)
    if not all(isinstance(value, Decimal) and value.is_finite() for value in prices):
        raise MarketDataProviderError(f"Provider returned non-finite prices for {symbol} at {bar.timestamp}.")
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high:
        raise MarketDataProviderError(f"Provider returned inconsistent OHLC values for {symbol} at {bar.timestamp}.")
    if bar.volume < 0 or bar.timestamp.tzinfo is None:
        raise MarketDataProviderError(f"Provider returned invalid volume or naive timestamp for {symbol} at {bar.timestamp}.")


class MarketDataProvider(ABC):
    """Interface for historical and latest market data retrieval."""

    @abstractmethod
    def fetch_historical(
        self, symbol: str, start: datetime, end: Optional[datetime], interval: str
    ) -> List[OHLCVBar]:
        """Return normalized bars in the requested interval and inclusive date range."""

    def fetch_latest(self, symbol: str, interval: str = "1m") -> Optional[OHLCVBar]:
        """Return the latest available bar, if the provider has any data."""
        from datetime import datetime, timezone

        end = datetime.now(timezone.utc)
        bars = self.fetch_historical(symbol, start=end - timedelta(days=7), end=end, interval=interval)
        return bars[-1] if bars else None
