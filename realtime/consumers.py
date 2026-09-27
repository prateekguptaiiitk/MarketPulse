"""Authenticated WebSocket consumers for instrument and watchlist price feeds."""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from instruments.models import Instrument
from watchlists.models import Watchlist


@database_sync_to_async
def _active_instrument_exists(instrument_id):
    return Instrument.objects.filter(pk=instrument_id, is_active=True).exists()


@database_sync_to_async
def _owned_watchlist_exists(watchlist_id, user_id):
    return Watchlist.objects.filter(pk=watchlist_id, user_id=user_id).exists()


class InstrumentPriceConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe one authenticated client to a single instrument's price group."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.instrument_id = self.scope["url_route"]["kwargs"]["instrument_id"]
        if not await _active_instrument_exists(self.instrument_id):
            await self.close(code=4404)
            return
        self.group_name = f"instrument_{self.instrument_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "instrument_id": self.instrument_id})

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def price_update(self, event):
        await self.send_json(event["data"])


class WatchlistPriceConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe only the owning user to all updates for a watchlist."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.watchlist_id = self.scope["url_route"]["kwargs"]["watchlist_id"]
        if not await _owned_watchlist_exists(self.watchlist_id, user.pk):
            await self.close(code=4404)
            return
        self.group_name = f"watchlist_{self.watchlist_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "watchlist_id": self.watchlist_id})

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def price_update(self, event):
        await self.send_json(event["data"])
