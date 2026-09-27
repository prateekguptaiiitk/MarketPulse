"""Load the starter equity catalog used by local development."""
from django.core.management.base import BaseCommand

from instruments.models import Instrument

STARTER_INSTRUMENTS = [
    ("RELIANCE.NS", "NSE", "Reliance Industries", "Energy"),
    ("TCS.NS", "NSE", "Tata Consultancy Services", "Information Technology"),
    ("INFY.NS", "NSE", "Infosys", "Information Technology"),
    ("HDFCBANK.NS", "NSE", "HDFC Bank", "Financial Services"),
    ("ICICIBANK.NS", "NSE", "ICICI Bank", "Financial Services"),
    ("AAPL", "NASDAQ", "Apple Inc.", "Technology"),
    ("MSFT", "NASDAQ", "Microsoft Corporation", "Technology"),
    ("NVDA", "NASDAQ", "NVIDIA Corporation", "Technology"),
    ("AMZN", "NASDAQ", "Amazon.com, Inc.", "Consumer Cyclical"),
    ("GOOGL", "NASDAQ", "Alphabet Inc.", "Communication Services"),
    ("TSLA", "NASDAQ", "Tesla, Inc.", "Consumer Cyclical"),
    ("JPM", "NYSE", "JPMorgan Chase & Co.", "Financial Services"),
]


class Command(BaseCommand):
    help = "Create or update the starter list of NSE and US instruments."

    def handle(self, *args, **options):
        for symbol, exchange, name, sector in STARTER_INSTRUMENTS:
            Instrument.objects.update_or_create(
                symbol=symbol,
                defaults={"exchange": exchange, "name": name, "sector": sector, "is_active": True},
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(STARTER_INSTRUMENTS)} instruments."))
