"""Pandas-based, provider-independent technical indicator calculations."""
from typing import Any, Dict, Mapping, Optional

import numpy as np
import pandas as pd


SUPPORTED_INDICATORS = {"sma", "ema", "rsi", "macd", "bollinger", "volume_spike"}


def _positive_int(params: Mapping[str, Any], key: str, default: int, minimum: int = 1) -> int:
    """Read and validate a positive integer indicator parameter."""
    value = int(params.get(key, default))
    if value < minimum:
        raise ValueError(f"{key} must be at least {minimum}.")
    return value


def _series_payload(index: pd.Index, values: pd.Series) -> list:
    """Convert a pandas series to JSON-safe timestamp/value rows."""
    result = []
    for timestamp, value in zip(index, values):
        clean_value = None if pd.isna(value) else float(value)
        result.append({"timestamp": timestamp.isoformat(), "value": clean_value})
    return result


def calculate_indicator(
    frame: pd.DataFrame, indicator: str, params: Optional[Mapping[str, Any]] = None
) -> Dict[str, Any]:
    """Calculate one named indicator over chronologically ordered OHLCV rows.

    Warm-up bars are retained and represented as ``None`` in output. This keeps
    each indicator aligned with source timestamps and makes charting predictable.
    """
    params = params or {}
    indicator = indicator.lower()
    if indicator not in SUPPORTED_INDICATORS:
        raise ValueError(f"Unsupported indicator '{indicator}'.")
    if frame.empty:
        return {"parameters": dict(params), "series": {}}

    close = pd.to_numeric(frame["close"], errors="coerce").astype(float)
    output: Dict[str, Any] = {"parameters": dict(params), "series": {}}

    if indicator == "sma":
        period = _positive_int(params, "period", 20)
        values = close.rolling(window=period, min_periods=period).mean()
        output["parameters"] = {"period": period}
        output["series"]["sma"] = _series_payload(frame.index, values)
    elif indicator == "ema":
        period = _positive_int(params, "period", 20)
        values = close.ewm(span=period, adjust=False, min_periods=period).mean()
        output["parameters"] = {"period": period}
        output["series"]["ema"] = _series_payload(frame.index, values)
    elif indicator == "rsi":
        period = _positive_int(params, "period", 14)
        delta = close.diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        # Seed Wilder's recursion with the first period's simple average, then
        # apply the canonical alpha=1/period smoothing to subsequent changes.
        average_gain = pd.Series(np.nan, index=frame.index, dtype=float)
        average_loss = pd.Series(np.nan, index=frame.index, dtype=float)
        if len(frame) > period:
            average_gain.iloc[period] = gains.iloc[1 : period + 1].mean()
            average_loss.iloc[period] = losses.iloc[1 : period + 1].mean()
            for position in range(period + 1, len(frame)):
                average_gain.iloc[position] = (average_gain.iloc[position - 1] * (period - 1) + gains.iloc[position]) / period
                average_loss.iloc[position] = (average_loss.iloc[position - 1] * (period - 1) + losses.iloc[position]) / period
        ratio = average_gain / average_loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + ratio)
        rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
        rsi = rsi.mask((average_gain == 0) & (average_loss > 0), 0)
        rsi = rsi.mask((average_gain == 0) & (average_loss == 0), 50)
        output["parameters"] = {"period": period}
        output["series"]["rsi"] = _series_payload(frame.index, rsi)
    elif indicator == "macd":
        fast = _positive_int(params, "fast", 12)
        slow = _positive_int(params, "slow", 26)
        signal_period = _positive_int(params, "signal", 9)
        if fast >= slow:
            raise ValueError("MACD fast period must be less than slow period.")
        macd_line = close.ewm(span=fast, adjust=False, min_periods=fast).mean() - close.ewm(span=slow, adjust=False, min_periods=slow).mean()
        signal_line = macd_line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
        output["parameters"] = {"fast": fast, "slow": slow, "signal": signal_period}
        output["series"]["macd"] = _series_payload(frame.index, macd_line)
        output["series"]["signal"] = _series_payload(frame.index, signal_line)
        output["series"]["histogram"] = _series_payload(frame.index, macd_line - signal_line)
    elif indicator == "bollinger":
        period = _positive_int(params, "period", 20)
        deviations = float(params.get("stddev", 2.0))
        if not np.isfinite(deviations) or deviations <= 0:
            raise ValueError("stddev must be a positive finite number.")
        middle = close.rolling(window=period, min_periods=period).mean()
        standard_deviation = close.rolling(window=period, min_periods=period).std(ddof=0)
        output["parameters"] = {"period": period, "stddev": deviations}
        output["series"]["middle"] = _series_payload(frame.index, middle)
        output["series"]["upper"] = _series_payload(frame.index, middle + deviations * standard_deviation)
        output["series"]["lower"] = _series_payload(frame.index, middle - deviations * standard_deviation)
    else:  # volume_spike
        period = _positive_int(params, "period", 20)
        threshold = float(params.get("threshold", 1.5))
        if not np.isfinite(threshold) or threshold <= 0:
            raise ValueError("threshold must be a positive finite number.")
        volume = pd.to_numeric(frame["volume"], errors="coerce").astype(float)
        baseline = volume.shift(1).rolling(window=period, min_periods=period).mean()
        ratio = volume / baseline.replace(0, np.nan)
        output["parameters"] = {"period": period, "threshold": threshold}
        output["series"]["ratio"] = _series_payload(frame.index, ratio)
        output["series"]["spike"] = [
            {"timestamp": timestamp.isoformat(), "value": bool(value) if pd.notna(value) else None}
            for timestamp, value in zip(frame.index, ratio >= threshold)
        ]
    return output
