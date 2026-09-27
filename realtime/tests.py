"""WebSocket authentication, authorization, and price polling tests."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from config.asgi import application
from instruments.models import Instrument, PriceBar
from market_data.providers.base import OHLCVBar
from realtime.tasks import poll_latest_prices
from watchlists.models import Watchlist, WatchlistItem


class RealtimeConsumerTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user("socket@example.com", "Strong-example-pass-734!")
        self.instrument = Instrument.objects.create(symbol="WS", name="WebSocket Equity")
        self.watchlist = Watchlist.objects.create(user=self.user, name="Live")
        WatchlistItem.objects.create(watchlist=self.watchlist, instrument=self.instrument)
        self.token = str(AccessToken.for_user(self.user))
        self.stranger = User.objects.create_user("stranger@example.com", "Strong-example-pass-734!")
        self.stranger_token = str(AccessToken.for_user(self.stranger))

    async def test_instrument_consumer_authenticates_and_receives_tick(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/prices/{self.instrument.pk}/?token={self.token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        self.assertEqual((await communicator.receive_json_from())["type"], "connected")
        tick = {"symbol": self.instrument.symbol, "close": "123.45"}
        await get_channel_layer().group_send(
            f"instrument_{self.instrument.pk}", {"type": "price.update", "data": tick}
        )
        self.assertEqual(await communicator.receive_json_from(), tick)
        await communicator.disconnect()

    async def test_websocket_rejects_anonymous_and_foreign_watchlist_clients(self):
        anonymous = WebsocketCommunicator(
            application, f"/ws/prices/{self.instrument.pk}/", headers=[(b"origin", b"http://localhost")]
        )
        connected, close_code = await anonymous.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)

        foreign = WebsocketCommunicator(
            application,
            f"/ws/watchlists/{self.watchlist.pk}/?token={self.stranger_token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, close_code = await foreign.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4404)


class PricePollingTaskTests(TransactionTestCase):
    @patch("realtime.tasks.get_market_data_provider")
    def test_poller_persists_and_only_publishes_new_bars(self, get_provider):
        instrument = Instrument.objects.create(symbol="POLL", name="Poll Equity")
        user = User.objects.create_user("poll@example.com", "Strong-example-pass-734!")
        watchlist = Watchlist.objects.create(user=user, name="Polling")
        WatchlistItem.objects.create(watchlist=watchlist, instrument=instrument)
        bar = OHLCVBar(
            timestamp=datetime.now(timezone.utc), open=Decimal("10"), high=Decimal("12"),
            low=Decimal("9"), close=Decimal("11"), volume=200,
        )
        get_provider.return_value.fetch_latest.return_value = bar

        first = poll_latest_prices.apply().result
        second = poll_latest_prices.apply().result

        self.assertEqual(first["bars_published"], 1)
        self.assertEqual(second["bars_published"], 0)
        self.assertEqual(PriceBar.objects.filter(instrument=instrument).count(), 1)
