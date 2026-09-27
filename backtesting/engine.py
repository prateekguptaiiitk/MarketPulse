"""Deterministic long-only backtest simulation over stored price bars."""
import math
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Sequence

import pandas as pd

from indicators.services import calculate_indicator
from instruments.models import PriceBar
from strategies.engine import evaluate_strategy


INDICATOR_SERIES = {
    "SMA": ("sma", "sma"),
    "EMA": ("ema", "ema"),
    "RSI": ("rsi", "rsi"),
    "MACD": ("macd", "macd"),
    "MACD_SIGNAL": ("macd", "signal"),
    "MACD_HISTOGRAM": ("macd", "histogram"),
    "BOLLINGER_UPPER": ("bollinger", "upper"),
    "BOLLINGER_MIDDLE": ("bollinger", "middle"),
    "BOLLINGER_LOWER": ("bollinger", "lower"),
    "VOLUME_SPIKE": ("volume_spike", "spike"),
    "VOLUME_SPIKE_RATIO": ("volume_spike", "ratio"),
}


def _utc_date_bound(value: str, *, inclusive_end: bool = False) -> datetime:
    """Convert an ISO date or datetime into a UTC query boundary."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if len(value) == 10:
        parsed = datetime.combine(parsed.date(), time.min, tzinfo=timezone.utc)
        if inclusive_end:
            parsed += timedelta(days=1)
    elif inclusive_end:
        parsed += timedelta(microseconds=1)
    return parsed.astimezone(timezone.utc)


def _precompute_indicator_series(frame: pd.DataFrame, rules: Sequence[Mapping[str, Any]]) -> Dict[str, List[Any]]:
    """Calculate each needed indicator once for the full dataset.

    Computing a rolling indicator once avoids recalculating every historical
    prefix during the bar-by-bar simulation (which would be quadratic).
    """
    names = {str(rule.get("indicator", "")).upper() for rule in rules}
    result: Dict[str, List[Any]] = {}
    calculated: Dict[str, Dict[str, Any]] = {}
    for name in names:
        mapping = INDICATOR_SERIES.get(name)
        if not mapping:
            continue
        calculation, series_name = mapping
        if calculation not in calculated:
            calculated[calculation] = calculate_indicator(frame, calculation)
        series = calculated[calculation].get("series", {}).get(series_name, [])
        result[name] = [point["value"] for point in series]
    return result


def simulate_backtest(
    bars: Sequence[PriceBar],
    strategy: Any,
    initial_capital: Decimal,
    *,
    interval: str = PriceBar.Interval.ONE_DAY,
) -> Dict[str, Any]:
    """Walk bars chronologically, buy on entry, sell on exit, and mark equity.

    Position sizing uses all available cash for one long position at a time.
    Signals execute at the bar close and no leverage or short positions are used.
    """
    if not bars:
        raise ValueError("No price bars are available for this date range and interval.")
    bars = sorted(bars, key=lambda bar: bar.timestamp)
    frame = pd.DataFrame({
        "close": [float(bar.close) for bar in bars],
        "volume": [float(bar.volume) for bar in bars],
    }, index=pd.to_datetime([bar.timestamp for bar in bars], utc=True))
    entry_rules = strategy.rules if hasattr(strategy, "rules") else strategy.get("rules", [])
    exit_rules = strategy.exit_rules if hasattr(strategy, "exit_rules") else strategy.get("exit_rules", [])
    required_rules = list(entry_rules) + list(exit_rules)
    values_by_indicator = _precompute_indicator_series(frame, required_rules)

    starting_cash = float(initial_capital)
    cash = starting_cash
    quantity = 0.0
    entry_price = 0.0
    entry_time = None
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []

    for index, bar in enumerate(bars):
        price = float(bar.close)
        snapshot = {name: points[index] for name, points in values_by_indicator.items()}
        if quantity == 0:
            if evaluate_strategy(strategy, snapshot).matched and price > 0:
                quantity = cash / price
                entry_price = price
                entry_time = bar.timestamp
                cash = 0.0
        elif evaluate_strategy(strategy, snapshot, exit_signal=True).matched:
            proceeds = quantity * price
            trades.append({
                "entry_time": entry_time.isoformat(),
                "exit_time": bar.timestamp.isoformat(),
                "entry_price": entry_price,
                "exit_price": price,
                "quantity": quantity,
                "pnl": proceeds - quantity * entry_price,
                "return_pct": (price / entry_price - 1.0) * 100.0,
            })
            cash = proceeds
            quantity = 0.0
            entry_price = 0.0
            entry_time = None
        equity = cash + quantity * price
        equity_curve.append({"timestamp": bar.timestamp.isoformat(), "equity": equity})

    final_equity = equity_curve[-1]["equity"]
    bar_returns = [
        equity_curve[index]["equity"] / equity_curve[index - 1]["equity"] - 1.0
        for index in range(1, len(equity_curve))
        if equity_curve[index - 1]["equity"] > 0
    ]
    average_return = sum(bar_returns) / len(bar_returns) if bar_returns else 0.0
    if len(bar_returns) > 1:
        variance = sum((value - average_return) ** 2 for value in bar_returns) / (len(bar_returns) - 1)
        volatility = math.sqrt(variance)
    else:
        volatility = 0.0
    annualization = {"1d": 252, "5m": 252 * 78, "1m": 252 * 390}.get(interval, 252)
    sharpe_ratio = (average_return / volatility * math.sqrt(annualization)) if volatility > 0 else 0.0

    peak = starting_cash
    max_drawdown = 0.0
    for point in equity_curve:
        peak = max(peak, point["equity"])
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - point["equity"]) / peak)
    winners = sum(1 for trade in trades if trade["pnl"] > 0)
    return {
        "metrics": {
            "total_return_pct": (final_equity / starting_cash - 1.0) * 100.0 if starting_cash else 0.0,
            "win_rate_pct": winners / len(trades) * 100.0 if trades else 0.0,
            "max_drawdown_pct": max_drawdown * 100.0,
            "sharpe_ratio": sharpe_ratio,
            "number_of_trades": len(trades),
            "starting_capital": starting_cash,
            "final_equity": final_equity,
            "open_position": quantity > 0,
        },
        "trades": trades,
        "equity_curve": equity_curve,
        "bars_processed": len(bars),
    }


def run_backtest_for_run(run_id: int) -> Dict[str, Any]:
    """Load a persisted run's inputs and produce deterministic simulation results."""
    from django.utils import timezone as django_timezone
    from backtesting.models import BacktestRun

    run = BacktestRun.objects.select_related("strategy", "instrument").get(pk=run_id)
    start = _utc_date_bound(run.date_range["start"])
    end = _utc_date_bound(run.date_range["end"], inclusive_end=True)
    bars = list(
        PriceBar.objects.filter(instrument=run.instrument, interval=run.interval, timestamp__gte=start, timestamp__lt=end)
        .order_by("timestamp")
    )
    result = simulate_backtest(bars, run.strategy, run.initial_capital, interval=run.interval)
    result["metadata"] = {
        "strategy_id": run.strategy_id,
        "instrument_id": run.instrument_id,
        "symbol": run.instrument.symbol,
        "interval": run.interval,
        "date_range": run.date_range,
        "completed_at": django_timezone.now().isoformat(),
    }
    return result
