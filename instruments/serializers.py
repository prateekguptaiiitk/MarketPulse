"""Serializers for instrument catalog and historical prices."""
from rest_framework import serializers

from .models import Instrument, PriceBar

'''
    We can use `fields = "__all__"` in both ModelSerializer's. It’s valid, but explicitly listing API fields is
    usually safer: if someone later adds a model field, '__all__' exposes it automatically without anyone reviewing
    whether it belongs in the API.
'''
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
