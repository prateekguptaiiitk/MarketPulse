"""Periodic polling and channel-layer publication of newly observed price bars."""
import logging
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from instruments.models import Instrument, PriceBar
from market_data.providers.base import MarketDataProviderError, validate_ohlcv_bar
from market_data.providers.factory import get_market_data_provider
from watchlists.models import WatchlistItem

logger = logging.getLogger(__name__)


@shared_task(name="realtime.poll_latest_prices")
def poll_latest_prices():
    """Poll active symbols and broadcast only bars newer than persisted data."""
    provider = get_market_data_provider()
    interval = settings.MARKET_DATA_POLL_INTERVAL
    channel_layer = get_channel_layer()
    symbols_polled = 0
    bars_published = 0
    failed = 0

    for instrument in Instrument.objects.filter(is_active=True).order_by("symbol").iterator(chunk_size=200):
        symbols_polled += 1
        try:
            bar = provider.fetch_latest(instrument.symbol, interval=interval)
            if bar is None:
                continue
            validate_ohlcv_bar(bar, instrument.symbol)
            previous = PriceBar.objects.filter(instrument=instrument, interval=interval).order_by("-timestamp").first()
            if previous and previous.timestamp >= bar.timestamp:
                continue
            with transaction.atomic():
                PriceBar.objects.update_or_create(
                    instrument=instrument,
                    timestamp=bar.timestamp,
                    interval=interval,
                    defaults={"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume},
                )
            data = {
                "type": "price_update",
                "instrument_id": instrument.pk,
                "symbol": instrument.symbol,
                "interval": interval,
                "timestamp": bar.timestamp.isoformat(),
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "volume": bar.volume,
            }
            async_to_sync(channel_layer.group_send)(f"instrument_{instrument.pk}", {"type": "price.update", "data": data})
            watchlist_ids = WatchlistItem.objects.filter(instrument=instrument).values_list("watchlist_id", flat=True).distinct()
            for watchlist_id in watchlist_ids.iterator(chunk_size=200):
                async_to_sync(channel_layer.group_send)(f"watchlist_{watchlist_id}", {"type": "price.update", "data": data})
            bars_published += 1
        except MarketDataProviderError:
            failed += 1
            logger.exception("Market provider failed polling %s", instrument.symbol)
        except Exception:
            failed += 1
            logger.exception("Failed to persist or broadcast a price bar for %s", instrument.symbol)
    return {"symbols_polled": symbols_polled, "bars_published": bars_published, "failed": failed}
