"""Watchlist serializers with write-safe ownership and membership validation."""
from rest_framework import serializers

from instruments.models import Instrument
from instruments.serializers import InstrumentSerializer
from .models import Watchlist, WatchlistItem


class WatchlistItemSerializer(serializers.ModelSerializer):
    instrument_detail = InstrumentSerializer(source="instrument", read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ("id", "watchlist", "instrument", "instrument_detail", "added_at")
        read_only_fields = ("id", "watchlist", "added_at")

    def validate_instrument(self, value: Instrument) -> Instrument:
        if not value.is_active:
            raise serializers.ValidationError("Inactive instruments cannot be added to a watchlist.")
        view = self.context.get("view")
        watchlist_id = self.context.get("watchlist_pk") or getattr(view, "kwargs", {}).get("watchlist_pk")
        duplicate_items = WatchlistItem.objects.filter(watchlist_id=watchlist_id, instrument=value) if watchlist_id else WatchlistItem.objects.none()
        if self.instance:
            duplicate_items = duplicate_items.exclude(pk=self.instance.pk)
        if duplicate_items.exists():
            raise serializers.ValidationError("This instrument is already in the watchlist.")
        return value


class WatchlistSerializer(serializers.ModelSerializer):
    items = WatchlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Watchlist
        fields = ("id", "name", "items", "created_at", "updated_at")
        read_only_fields = ("id", "items", "created_at", "updated_at")
