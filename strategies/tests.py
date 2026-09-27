"""Strategy engine and API tests with local, deterministic indicator values."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from strategies.engine import evaluate_rules, evaluate_strategy
from strategies.models import Strategy


class StrategyEvaluationTests(TestCase):
    def test_and_returns_true_only_when_every_rule_matches(self):
        rules = [
            {"indicator": "RSI", "condition": "less_than", "value": 30},
            {"indicator": "SMA", "condition": "greater_than", "value": 100},
        ]
        result = evaluate_rules(rules, "AND", {"rsi": 25.0, "sma": 105.0})

        self.assertTrue(result.matched)
        self.assertEqual(len(result.matched_conditions), 2)
        failed = evaluate_rules(rules, "AND", {"RSI": 25.0, "SMA": 95.0})
        self.assertFalse(failed.matched)
        self.assertEqual(len(failed.matched_conditions), 1)

    def test_or_and_boolean_volume_conditions(self):
        rules = [
            {"indicator": "RSI", "condition": "less_than", "value": 20},
            {"indicator": "VOLUME_SPIKE", "condition": "is_true"},
        ]
        result = evaluate_rules(rules, "OR", {"RSI": 45.0, "VOLUME_SPIKE": True})
        self.assertTrue(result.matched)
        self.assertEqual(result.matched_conditions[0]["rule"]["indicator"], "VOLUME_SPIKE")
        self.assertFalse(evaluate_rules([], "OR", {"RSI": 10.0}).matched)

    def test_engine_reads_latest_value_from_indicator_endpoint_shape_and_exit_rules(self):
        strategy = {
            "rules": [{"indicator": "RSI", "condition": "less_than_or_equal", "value": 30}],
            "logic": "AND",
            "exit_rules": [{"indicator": "MACD_SIGNAL", "condition": "greater_than", "value": 0}],
            "exit_logic": "OR",
        }
        snapshot = {
            "indicators": {
                "rsi": {"series": {"rsi": [{"timestamp": "t1", "value": 40}, {"timestamp": "t2", "value": 28}]}},
                "macd": {"series": {"signal": [{"timestamp": "t2", "value": 0.2}]}},
            }
        }
        self.assertTrue(evaluate_strategy(strategy, snapshot).matched)
        self.assertTrue(evaluate_strategy(strategy, snapshot, exit_signal=True).matched)

    def test_missing_indicator_never_matches_and_invalid_logic_is_rejected(self):
        rules = [{"indicator": "RSI", "condition": "less_than", "value": 30}]
        self.assertFalse(evaluate_rules(rules, "AND", {}).matched)
        with self.assertRaises(ValueError):
            evaluate_rules(rules, "XOR", {"RSI": 10})


class StrategyApiTests(TestCase):
    def test_strategy_crud_is_owned_and_rule_payloads_are_validated(self):
        owner = User.objects.create_user("owner@example.com", "Strong-example-pass-734!")
        other = User.objects.create_user("other@example.com", "Strong-example-pass-734!")
        client = APIClient()
        client.force_authenticate(owner)
        response = client.post("/api/v1/strategies/", {
            "name": "Mean reversion",
            "logic": "AND",
            "rules": [{"indicator": "rsi", "condition": "less_than", "value": 30}],
            "exit_logic": "OR",
            "exit_rules": [{"indicator": "MACD_SIGNAL", "condition": "greater_than", "value": 0}],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        strategy = Strategy.objects.get()
        self.assertEqual(strategy.user, owner)
        self.assertEqual(strategy.rules[0]["indicator"], "RSI")

        invalid = client.post("/api/v1/strategies/", {
            "name": "Bad", "rules": [{"indicator": "RSI", "condition": "less_than"}],
        }, format="json")
        self.assertEqual(invalid.status_code, 400)

        client.force_authenticate(other)
        self.assertEqual(client.get(f"/api/v1/strategies/{strategy.pk}/").status_code, 404)
        self.assertEqual(client.delete(f"/api/v1/strategies/{strategy.pk}/").status_code, 404)
