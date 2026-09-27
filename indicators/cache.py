"""Redis-backed cache helpers for computed indicator series."""
import hashlib
import json
from typing import Any, Dict, Mapping

from django.conf import settings
from django.core.cache import cache

from .services import calculate_indicator


def cached_indicator(instrument_id: int, interval: str, indicator: str, params: Mapping[str, Any], frame):
    """Return cached results or calculate and cache one indicator series."""
    cache_params = dict(params)
    cache_params["lookback"] = len(frame.index)
    serialized = json.dumps(cache_params, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
    key = f"marketpulse:indicator:v1:{instrument_id}:{interval}:{indicator}:{digest}"
    result = cache.get(key)
    if result is None:
        result = calculate_indicator(frame, indicator, params)
        cache.set(key, result, timeout=settings.INDICATOR_CACHE_TTL)
    return result
