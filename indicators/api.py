"""Indicators endpoint for instrument historical bars."""
from decimal import Decimal

import pandas as pd
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from instruments.models import Instrument, PriceBar
from .cache import cached_indicator
from .services import SUPPORTED_INDICATORS


class InstrumentIndicatorsView(APIView):
    """Compute requested technical indicators over the latest N price bars."""

    permission_classes = [permissions.IsAuthenticated]
    parameter_names = ("period", "fast", "slow", "signal", "stddev", "threshold")

    def get(self, request, instrument_id, version=None):
        instrument = get_object_or_404(Instrument, pk=instrument_id, is_active=True)
        interval = request.query_params.get("interval", PriceBar.Interval.ONE_DAY)
        if interval not in PriceBar.Interval.values:
            return Response({"detail": "Unsupported interval."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lookback = int(request.query_params.get("lookback", "100"))
        except (TypeError, ValueError):
            return Response({"detail": "lookback must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= lookback <= 2000:
            return Response({"detail": "lookback must be between 1 and 2000."}, status=status.HTTP_400_BAD_REQUEST)

        requested = request.query_params.get("indicators", ",".join(sorted(SUPPORTED_INDICATORS)))
        indicators = [name.strip().lower() for name in requested.split(",") if name.strip()]
        invalid = sorted(set(indicators) - SUPPORTED_INDICATORS)
        if not indicators or invalid:
            return Response(
                {"detail": "Choose one or more supported indicators.", "supported": sorted(SUPPORTED_INDICATORS), "invalid": invalid},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(set(indicators)) != len(indicators):
            return Response({"detail": "Duplicate indicator names are not allowed."}, status=status.HTTP_400_BAD_REQUEST)
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
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "instrument": {"id": instrument.id, "symbol": instrument.symbol},
            "interval": interval,
            "lookback": len(bars),
            "indicators": results,
        })
