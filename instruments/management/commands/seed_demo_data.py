"""Seed the starter catalog and deterministic daily bars for local demos."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone as django_timezone

from instruments.management.commands.seed_instruments import STARTER_INSTRUMENTS
from instruments.models import Instrument, PriceBar


class Command(BaseCommand):
    help = "Seed 12 sample instruments and deterministic historical daily bars without market API access."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=10, help="Number of calendar days to generate (1-90).")

    def handle(self, *args, **options):
        days = options["days"]
        if not 1 <= days <= 90:
            raise CommandError("--days must be between 1 and 90.")
        today = django_timezone.now().date()
        rows = 0
        with transaction.atomic():
            instruments = []
            for symbol, exchange, name, sector in STARTER_INSTRUMENTS:
                instrument, _ = Instrument.objects.update_or_create(
                    symbol=symbol,
                    defaults={"exchange": exchange, "name": name, "sector": sector, "is_active": True},
                )
                instruments.append(instrument)
            for instrument_index, instrument in enumerate(instruments):
                base = Decimal("50") + Decimal(instrument_index * 35)
                for day_index in range(days):
                    trading_date = today - timedelta(days=days - day_index - 1)
                    timestamp = datetime.combine(trading_date, time.min, tzinfo=timezone.utc)
                    oscillation = Decimal((day_index % 5) - 2) * Decimal("0.37")
                    close = (base + Decimal(day_index) * Decimal("0.82") + oscillation).quantize(Decimal("0.01"))
                    open_price = (close - Decimal("0.23")).quantize(Decimal("0.01"))
                    low = (min(open_price, close) - Decimal("0.61")).quantize(Decimal("0.01"))
                    high = (max(open_price, close) + Decimal("0.74")).quantize(Decimal("0.01"))
                    PriceBar.objects.update_or_create(
                        instrument=instrument,
                        timestamp=timestamp,
                        interval=PriceBar.Interval.ONE_DAY,
                        defaults={
                            "open": open_price,
                            "high": high,
                            "low": low,
                            "close": close,
                            "volume": 100_000 + instrument_index * 10_000 + day_index * 750,
                        },
                    )
                    rows += 1
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(instruments)} instruments and {rows} deterministic daily bars over {days} days."
        ))
