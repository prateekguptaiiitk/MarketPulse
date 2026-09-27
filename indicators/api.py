"""Indicators endpoint for instrument historical bars."""
from decimal import Decimal

import pandas as pd
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiParameter, extend_schema

from instruments.models import Instrument, PriceBar
from .cache import cached_indicator
from .services import SUPPORTED_INDICATORS


class IndicatorValueSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    value = serializers.JSONField(allow_null=True)


class IndicatorResultSerializer(serializers.Serializer):
    parameters = serializers.DictField(child=serializers.JSONField())
    series = serializers.DictField(child=serializers.ListField(child=IndicatorValueSerializer()))


class IndicatorsResponseSerializer(serializers.Serializer):
    instrument = serializers.DictField(child=serializers.JSONField())
    interval = serializers.CharField()
    lookback = serializers.IntegerField()
    indicators = serializers.DictField(child=IndicatorResultSerializer())


class InstrumentIndicatorsView(APIView):
    """Compute requested technical indicators over the latest N price bars."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IndicatorsResponseSerializer
    parameter_names = ("period", "fast", "slow", "signal", "stddev", "threshold")

    @extend_schema(
        parameters=[
            OpenApiParameter("indicators", str, description="Comma-separated SMA, EMA, RSI, MACD, Bollinger, and volume_spike."),
            OpenApiParameter("lookback", int, description="Number of bars to include (1-2000)."),
            OpenApiParameter("interval", str, description="Price bar interval: 1m, 5m, or 1d."),
        ],
        responses=IndicatorsResponseSerializer,
    )
    def get(self, request, instrument_id, version=None):
        instrument = get_object_or_404(Instrument, pk=instrument_id, is_active=True)
        interval = request.query_params.get("interval", PriceBar.Interval.ONE_DAY)
        if interval not in PriceBar.Interval.values:
            raise ValidationError({"interval": "Unsupported interval."})
        try:
            lookback = int(request.query_params.get("lookback", "100"))
        except (TypeError, ValueError):
            raise ValidationError({"lookback": "Must be an integer."})
        if not 1 <= lookback <= 2000:
            raise ValidationError({"lookback": "Must be between 1 and 2000."})

        requested = request.query_params.get("indicators", ",".join(sorted(SUPPORTED_INDICATORS)))
        indicators = [name.strip().lower() for name in requested.split(",") if name.strip()]
        invalid = sorted(set(indicators) - SUPPORTED_INDICATORS)
        if not indicators or invalid:
            raise ValidationError({"indicators": {"supported": sorted(SUPPORTED_INDICATORS), "invalid": invalid}})
        if len(set(indicators)) != len(indicators):
            raise ValidationError({"indicators": "Duplicate indicator names are not allowed."})
        params = {key: request.query_params[key] for key in self.parameter_names if key in request.query_params}

        bars = list(
            PriceBar.objects.filter(instrument=instrument, interval=interval)
            .order_by("-timestamp")
            .values("timestamp", "open", "high", "low", "close", "volume")[:lookback]
        )
        bars.reverse()
        frame = pd.DataFrame.from_records(bars)
        if not frame.empty:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            frame = frame.set_index("timestamp")
            for column in ("open", "high", "low", "close"):
                frame[column] = frame[column].map(lambda value: float(Decimal(value)))

        results = {}
        try:
            for indicator in indicators:
                results[indicator] = cached_indicator(instrument.id, interval, indicator, params, frame)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"indicators": str(exc)}) from exc

        return Response({
            "instrument": {"id": instrument.id, "symbol": instrument.symbol},
            "interval": interval,
            "lookback": len(bars),
            "indicators": results,
        })
