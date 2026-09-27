"""WebSocket URL patterns."""
from django.urls import path

from .consumers import InstrumentPriceConsumer, WatchlistPriceConsumer

websocket_urlpatterns = [
    path("ws/prices/<int:instrument_id>/", InstrumentPriceConsumer.as_asgi()),
    path("ws/watchlists/<int:watchlist_id>/", WatchlistPriceConsumer.as_asgi()),
]
