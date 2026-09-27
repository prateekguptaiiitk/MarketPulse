"""Backfill instrument price bars through the configured data provider."""
from datetime import datetime, time, timezone
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from instruments.models import Instrument, PriceBar
from market_data.providers.base import MarketDataProviderError, OHLCVBar, validate_ohlcv_bar
from market_data.providers.factory import get_market_data_provider


def parse_bound(value: Optional[str], *, end_of_day: bool = False) -> Optional[datetime]:
    """Parse an ISO date/datetime bound and normalize it to UTC."""
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        parsed_date = parse_date(value)
        if parsed_date is None:
            raise CommandError(f"Invalid ISO date/datetime: {value}")
        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_bar(bar: OHLCVBar, symbol: str) -> None:
    """Reject malformed provider rows before they reach persistent storage."""
    try:
        validate_ohlcv_bar(bar, symbol)
    except MarketDataProviderError as exc:
        raise CommandError(str(exc)) from exc


class Command(BaseCommand):
    help = "Backfill historical OHLCV bars for active instruments. End dates are inclusive."

    def add_arguments(self, parser):
        parser.add_argument("--symbols", nargs="+", help="Optional instrument symbols; defaults to all active instruments.")
        parser.add_argument("--start", required=True, help="Inclusive ISO start date or datetime.")
        parser.add_argument("--end", help="Inclusive ISO end date or datetime (defaults to latest available).")
        parser.add_argument("--interval", choices=PriceBar.Interval.values, default=PriceBar.Interval.ONE_DAY)
        parser.add_argument("--provider", help="Override MARKET_DATA_PROVIDER for this invocation.")

    def handle(self, *args, **options):
        start = parse_bound(options["start"])
        end = parse_bound(options.get("end"), end_of_day=True)
        if end is not None and start is not None and end < start:
            raise CommandError("--end must be on or after --start.")
        try:
            provider = get_market_data_provider(options.get("provider"))
        except MarketDataProviderError as exc:
            raise CommandError(str(exc)) from exc

        instruments = Instrument.objects.filter(is_active=True)
        symbols = options.get("symbols")
        if symbols:
            instruments = instruments.filter(symbol__in=symbols)
            found = set(instruments.values_list("symbol", flat=True))
            missing = sorted(set(symbols) - found)
            if missing:
                raise CommandError(f"Unknown or inactive symbols: {', '.join(missing)}")
        instruments = list(instruments.order_by("symbol"))
        if not instruments:
            self.stdout.write("No active instruments to backfill.")
            return

        total = 0
        for instrument in instruments:
            try:
                bars = provider.fetch_historical(instrument.symbol, start, end, options["interval"])
                for bar in bars:
                    validate_bar(bar, instrument.symbol)
                rows = [
                    PriceBar(
                        instrument=instrument,
                        timestamp=bar.timestamp,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        interval=options["interval"],
                    )
                    for bar in bars
                ]
                with transaction.atomic():
                    PriceBar.objects.bulk_create(
                        rows,
                        batch_size=500,
                        update_conflicts=True,
                        unique_fields=["instrument", "timestamp", "interval"],
                        update_fields=["open", "high", "low", "close", "volume"],
                    )
                total += len(rows)
                self.stdout.write(f"{instrument.symbol}: upserted {len(rows)} {options['interval']} bars")
            except MarketDataProviderError as exc:
                raise CommandError(f"Backfill failed for {instrument.symbol}: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Backfill complete: {total} bars processed across {len(instruments)} instruments."))
