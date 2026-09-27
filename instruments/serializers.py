"""Serializers for instrument catalog and historical prices."""
from rest_framework import serializers

from .models import Instrument, PriceBar


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ("id", "symbol", "exchange", "name", "sector", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PriceBarSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceBar
        fields = ("id", "instrument", "timestamp", "open", "high", "low", "close", "volume", "interval")
        read_only_fields = fields
