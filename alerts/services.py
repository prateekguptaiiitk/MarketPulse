"""Condition evaluation and concurrency-safe alert trigger recording."""
from datetime import timedelta
import logging
from typing import Any, Dict

import pandas as pd
from django.db import transaction
from django.utils import timezone

from alerts.models import Alert, AlertTriggerLog
from alerts.notifications import deliver_alert
from indicators.services import calculate_indicator
from instruments.models import PriceBar
from strategies.engine import evaluate_rules

logger = logging.getLogger(__name__)

INDICATOR_SERIES = {
    "SMA": ("sma", "sma"), "EMA": ("ema", "ema"), "RSI": ("rsi", "rsi"),
    "MACD": ("macd", "macd"), "MACD_SIGNAL": ("macd", "signal"),
    "MACD_HISTOGRAM": ("macd", "histogram"),
    "BOLLINGER_UPPER": ("bollinger", "upper"), "BOLLINGER_MIDDLE": ("bollinger", "middle"),
    "BOLLINGER_LOWER": ("bollinger", "lower"), "VOLUME_SPIKE": ("volume_spike", "spike"),
    "VOLUME_SPIKE_RATIO": ("volume_spike", "ratio"),
}

'''
    chooses which rules to evaluate. If the alert references a strategy, it uses that strategy’s rules and logic.
    Otherwise it uses the alert’s own condition rules and logic.
'''
def alert_rules(alert: Alert):
    """Return the rules and combination logic for a strategy or ad hoc alert."""
    if alert.strategy_id:
        return alert.strategy.rules, alert.strategy.logic

    condition = alert.condition or {}

    return condition.get("rules", []), condition.get("logic", "AND")

'''
     loads up to the latest 100 price bars for the alert’s instrument and interval. It calculates only the indicators
     the alert’s rules use, then returns their latest values along with the current PRICE.
'''
def latest_indicator_snapshot(alert: Alert, close_price: float) -> Dict[str, Any]:
    """Compute just the values referenced by a rule set from recent stored bars."""
    rules, _ = alert_rules(alert)
    names = {str(rule["indicator"]).upper() for rule in rules}
    values: Dict[str, Any] = {"PRICE": close_price}

    if not names.intersection(INDICATOR_SERIES):
        return values

    bars = list(
        PriceBar.objects.filter(instrument=alert.instrument, interval=alert.interval)
        .order_by("-timestamp").values("timestamp", "close", "volume")[:100]
    )
    bars.reverse()

    if not bars:
        return values

    frame = pd.DataFrame.from_records(bars)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)

    frame = frame.set_index("timestamp")
    frame["close"] = frame["close"].map(float)
    frame["volume"] = frame["volume"].map(float)

    computed = {}
    for name in names:
        mapping = INDICATOR_SERIES.get(name)

        if mapping is None:
            continue

        calculation, series_name = mapping

        if calculation not in computed:
            computed[calculation] = calculate_indicator(frame, calculation)

        series = computed[calculation].get("series", {}).get(series_name, [])
        values[name] = series[-1]["value"] if series else None

    return values

'''
     gets the latest price bar, builds an indicator snapshot, and evaluates the selected rules. It returns whether
     the alert matched, the price and timestamp, and the condition results. If there are no price bars, it reports no_price_data.
'''
def evaluate_alert(alert: Alert) -> Dict[str, Any]:
    """Evaluate one alert against its most recent persisted price bar."""
    latest = PriceBar.objects.filter(instrument=alert.instrument, interval=alert.interval).order_by("-timestamp").first()

    if latest is None:
        return {"triggered": False, "reason": "no_price_data"}

    rules, logic = alert_rules(alert)
    snapshot = latest_indicator_snapshot(alert, float(latest.close))
    outcome = evaluate_rules(rules, logic, snapshot)

    return {
        "triggered": outcome.matched,
        "price": str(latest.close),
        "timestamp": latest.timestamp.isoformat(),
        "logic": outcome.logic,
        "conditions": outcome.conditions,
        "matched_conditions": outcome.matched_conditions,
    }

'''
    runs the evaluation, checks that the alert is active and outside its cooldown, then records an AlertTriggerLog
    and updates last_triggered_at. It sends the notification and records whether delivery succeeded or failed.
'''
def trigger_alert(alert_id: int) -> bool:
    """Record and deliver an alert once per cooldown window, safely across workers."""
    alert = Alert.objects.select_related("instrument", "user", "strategy").get(pk=alert_id)

    if not alert.is_active:
        return False

    result = evaluate_alert(alert)
    if not result["triggered"]:
        return False

    with transaction.atomic():
        # Lock only the alert row. ``strategy`` is nullable, so asking PostgreSQL
        # to lock every row selected by select_related() attempts to lock the
        # nullable side of an outer join and raises FeatureNotSupported.
        locked_alert = (
            Alert.objects.select_for_update(of=("self",))
            .select_related("instrument", "user", "strategy")
            .get(pk=alert_id)
        )

        if not locked_alert.is_active:
            return False

        now = timezone.now()
        if locked_alert.last_triggered_at and locked_alert.last_triggered_at > now - timedelta(minutes=locked_alert.cooldown_minutes):
            return False

        log = AlertTriggerLog.objects.create(
            alert=locked_alert,
            price=result.get("price"),
            condition_results=result,
            delivery_status=AlertTriggerLog.DeliveryStatus.PENDING,
        )

        locked_alert.last_triggered_at = now
        locked_alert.save(update_fields=["last_triggered_at", "updated_at"])

    payload = {
        "event": "alert.triggered",
        "alert_id": locked_alert.id,
        "alert_name": locked_alert.name,
        "symbol": locked_alert.instrument.symbol,
        "price": result.get("price"),
        "triggered_at": now.isoformat(),
        "conditions": result.get("matched_conditions", []),
    }

    try:
        deliver_alert(locked_alert, payload)
    except Exception as exc:
        log.delivery_status = AlertTriggerLog.DeliveryStatus.FAILED
        log.delivery_error = str(exc)
        logger.exception("Failed to deliver alert %s", locked_alert.id)
    else:
        log.delivery_status = AlertTriggerLog.DeliveryStatus.SENT

    log.save(update_fields=["delivery_status", "delivery_error"])

    return True
