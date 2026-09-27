"""yfinance implementation of the provider contract."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from .base import MarketDataProvider, MarketDataProviderError, OHLCVBar


class YFinanceProvider(MarketDataProvider):
    """Fetch historical prices through yfinance and normalize pandas rows."""

    def fetch_historical(
        self, symbol: str, start: datetime, end: Optional[datetime], interval: str
    ) -> List[OHLCVBar]:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise MarketDataProviderError("Install yfinance to use the configured provider.") from exc

        try:
            frame = yf.download(
                tickers=symbol, start=start.date().isoformat(),
                # yfinance treats end as exclusive; extend a day then filter
                # rows to the provider-neutral inclusive end bound.
                end=(end.date() + timedelta(days=1)).isoformat() if end else None,
                interval=interval, auto_adjust=False, progress=False, threads=False,
            )
        except Exception as exc:  # Provider library raises several transport-specific errors.
            raise MarketDataProviderError(f"yfinance failed for {symbol}: {exc}") from exc
        return self._normalize_frame(frame, symbol, start, end)

    def fetch_latest(self, symbol: str, interval: str = "1m") -> Optional[OHLCVBar]:
        """Download only the latest trading day instead of a full history window."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise MarketDataProviderError("Install yfinance to use the configured provider.") from exc
        try:
            frame = yf.download(
                tickers=symbol, period="1d", interval=interval,
                auto_adjust=False, progress=False, threads=False,
            )
        except Exception as exc:
            raise MarketDataProviderError(f"yfinance failed for {symbol}: {exc}") from exc
        bars = self._normalize_frame(frame, symbol, None, None)
        return bars[-1] if bars else None

    @staticmethod
    def _normalize_frame(frame, symbol: str, start: Optional[datetime], end: Optional[datetime]) -> List[OHLCVBar]:
        """Convert yfinance's version-dependent DataFrame into validated bars."""
        if frame is None or frame.empty:
            return []

        # Recent yfinance versions can return a two-level (Price, Ticker) header.
        if getattr(frame.columns, "nlevels", 1) > 1:
            frame.columns = frame.columns.get_level_values(0)
        bars: List[OHLCVBar] = []
        for index, row in frame.iterrows():
            try:
                timestamp = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                timestamp = timestamp.astimezone(timezone.utc)
                bar = OHLCVBar(
                        timestamp=timestamp,
                        open=Decimal(str(row["Open"])),
                        high=Decimal(str(row["High"])),
                        low=Decimal(str(row["Low"])),
                        close=Decimal(str(row["Close"])),
                        volume=max(0, int(row["Volume"])),
                    )
                after_start = start is None or timestamp >= start.astimezone(timezone.utc)
                before_end = end is None or timestamp <= end.astimezone(timezone.utc)
                if after_start and before_end:
                    bars.append(bar)
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                raise MarketDataProviderError(f"Invalid OHLCV row returned for {symbol}: {exc}") from exc
        return bars
