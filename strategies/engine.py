"""Pure strategy condition evaluation independent of database and vendors."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional


SUPPORTED_INDICATORS = {
    "SMA", "EMA", "RSI", "MACD", "MACD_SIGNAL", "MACD_HISTOGRAM",
    "BOLLINGER_UPPER", "BOLLINGER_MIDDLE", "BOLLINGER_LOWER", "PRICE",
    "VOLUME_SPIKE", "VOLUME_SPIKE_RATIO",
}
SUPPORTED_CONDITIONS = {
    "greater_than", "less_than", "greater_than_or_equal", "less_than_or_equal",
    "equals", "not_equals", "is_true", "is_false",
}


@dataclass(frozen=True)
class EvaluationResult:
    """Overall rule result together with every rule's observed outcome."""

    matched: bool
    logic: str
    conditions: List[Dict[str, Any]]

    @property
    def matched_conditions(self) -> List[Dict[str, Any]]:
        """Return only the conditions that evaluated to true."""
        return [condition for condition in self.conditions if condition["matched"]]


def _latest_from_series(value: Any) -> Any:
    """Extract the newest value from the indicator API's aligned series format."""
    if isinstance(value, list):
        for item in reversed(value):
            if isinstance(item, Mapping) and item.get("value") is not None:
                return item["value"]
        return None
    return value


def _resolve_indicator(snapshot: Mapping[str, Any], indicator: str) -> Any:
    """Read a canonical flat indicator or the nested indicator API response."""
    key = indicator.upper()
    direct = {str(name).upper(): value for name, value in snapshot.items()}
    # Accept the indicator endpoint response:
    # {"rsi": {"series": {"rsi": [{"timestamp": ..., "value": ...}]}}}.
    api_name, series_name = {
        "MACD_SIGNAL": ("macd", "signal"),
        "MACD_HISTOGRAM": ("macd", "histogram"),
        "BOLLINGER_UPPER": ("bollinger", "upper"),
        "BOLLINGER_MIDDLE": ("bollinger", "middle"),
        "BOLLINGER_LOWER": ("bollinger", "lower"),
        "VOLUME_SPIKE": ("volume_spike", "spike"),
        "VOLUME_SPIKE_RATIO": ("volume_spike", "ratio"),
    }.get(key, (key.lower(), key.lower()))
    block = direct.get(key, snapshot.get(api_name, snapshot.get("indicators", {}).get(api_name, {})))
    if not isinstance(block, Mapping):
        return _latest_from_series(block)
    series = block.get("series", block)
    if not isinstance(series, Mapping):
        return None
    return _latest_from_series(series.get(series_name, block.get(series_name)))


def _matches(actual: Any, condition: str, expected: Any) -> bool:
    """Evaluate one comparison while treating missing values as non-matches."""
    if actual is None:
        return False
    if condition == "is_true":
        return actual is True
    if condition == "is_false":
        return actual is False
    try:
        if condition == "greater_than":
            return actual > expected
        if condition == "less_than":
            return actual < expected
        if condition == "greater_than_or_equal":
            return actual >= expected
        if condition == "less_than_or_equal":
            return actual <= expected
        if condition == "equals":
            return actual == expected
        if condition == "not_equals":
            return actual != expected
    except TypeError:
        return False
    return False


def evaluate_rules(rules: Iterable[Mapping[str, Any]], logic: str, snapshot: Mapping[str, Any]) -> EvaluationResult:
    """Evaluate structured rules against a current indicator snapshot.

    An empty rule set is false for both modes, preventing an incomplete strategy
    from accidentally generating an entry or exit signal.
    """
    logic = str(logic).upper()
    if logic not in ("AND", "OR"):
        raise ValueError("logic must be AND or OR")
    outcomes: List[Dict[str, Any]] = []
    for rule in rules:
        indicator = str(rule.get("indicator", "")).upper()
        condition = str(rule.get("condition", ""))
        actual = _resolve_indicator(snapshot, indicator)
        expected = rule.get("value")
        outcomes.append({
            "rule": dict(rule),
            "actual_value": actual,
            "matched": _matches(actual, condition, expected),
        })
    matched = bool(outcomes) and (all(item["matched"] for item in outcomes) if logic == "AND" else any(item["matched"] for item in outcomes))
    return EvaluationResult(matched=matched, logic=logic, conditions=outcomes)


def evaluate_strategy(strategy: Any, indicator_snapshot: Mapping[str, Any], *, exit_signal: bool = False) -> EvaluationResult:
    """Evaluate entry rules by default, or the strategy's exit rule set."""
    rules = getattr(strategy, "exit_rules" if exit_signal else "rules", None)
    logic = getattr(strategy, "exit_logic" if exit_signal else "logic", None)
    if isinstance(strategy, Mapping):
        rules = strategy.get("exit_rules" if exit_signal else "rules", [])
        logic = strategy.get("exit_logic" if exit_signal else "logic", "OR" if exit_signal else "AND")
    return evaluate_rules(rules or [], logic or "AND", indicator_snapshot)
