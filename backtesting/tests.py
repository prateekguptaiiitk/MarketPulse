"""Deterministic engine, task, and API tests for asynchronous backtests."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from backtesting.engine import run_backtest_for_run, simulate_backtest
from backtesting.models import BacktestRun
from backtesting.tasks import run_backtest
from instruments.models import Instrument, PriceBar
from strategies.models import Strategy


def create_fixture_bars(instrument, closes):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        PriceBar.objects.create(
            instrument=instrument,
            timestamp=start + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            interval=PriceBar.Interval.ONE_DAY,
        )
        for index, close in enumerate(closes)
    ]


class BacktestEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("backtest@example.com", "Strong-example-pass-734!")
        self.instrument = Instrument.objects.create(symbol="BT", name="Backtest Equity")
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="RSI reversal",
            rules=[{"indicator": "RSI", "condition": "less_than", "value": 50}],
            logic="AND",
            exit_rules=[{"indicator": "RSI", "condition": "greater_than", "value": 50}],
            exit_logic="OR",
        )
        self.bars = create_fixture_bars(self.instrument, list(range(120, 100, -1)) + list(range(101, 121)) + list(range(120, 100, -1)))

    def test_backtest_simulates_trades_and_returns_risk_metrics(self):
        results = simulate_backtest(self.bars, self.strategy, Decimal("10000"))

        metrics = results["metrics"]
        self.assertEqual(results["bars_processed"], len(self.bars))
        self.assertGreaterEqual(metrics["number_of_trades"], 1)
        self.assertGreater(metrics["final_equity"], 0)
        self.assertGreaterEqual(metrics["win_rate_pct"], 0)
        self.assertGreaterEqual(metrics["max_drawdown_pct"], 0)
        self.assertEqual(len(results["equity_curve"]), len(self.bars))

    def test_persisted_run_uses_requested_date_range(self):
        run = BacktestRun.objects.create(
            requested_by=self.user,
            strategy=self.strategy,
            instrument=self.instrument,
            date_range={"start": "2025-01-05", "end": "2025-01-10"},
            initial_capital=Decimal("10000"),
        )
        result = run_backtest_for_run(run.pk)
        self.assertEqual(result["bars_processed"], 6)
        self.assertEqual(result["metadata"]["symbol"], "BT")

    def test_celery_task_persists_completion_status(self):
        run = BacktestRun.objects.create(
            requested_by=self.user,
            strategy=self.strategy,
            instrument=self.instrument,
            date_range={"start": "2025-01-01", "end": "2025-02-28"},
            initial_capital=Decimal("10000"),
        )
        task_result = run_backtest.apply(args=(run.pk,))
        run.refresh_from_db()
        self.assertEqual(task_result.result["status"], BacktestRun.Status.COMPLETED)
        self.assertEqual(run.status, BacktestRun.Status.COMPLETED)
        self.assertIn("metrics", run.results)


class BacktestApiTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.com", "Strong-example-pass-734!")
        self.other = User.objects.create_user("other@example.com", "Strong-example-pass-734!")
        self.instrument = Instrument.objects.create(symbol="API", name="API Equity")
        self.strategy = Strategy.objects.create(
            user=self.owner,
            name="Entry rule",
            rules=[{"indicator": "RSI", "condition": "less_than", "value": 30}],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    @patch("backtesting.api.views.run_backtest.delay", return_value=SimpleNamespace(id="async-123"))
    def test_create_enqueues_a_run_and_returns_task_id(self, delay):
        response = self.client.post("/api/v1/backtests/", {
            "strategy": self.strategy.pk,
            "instrument": self.instrument.pk,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "initial_capital": "10000.00",
            "interval": "1d",
        }, format="json")

        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data["task_id"], "async-123")
        delay.assert_called_once_with(response.data["id"])

    def test_run_results_are_private_and_input_is_validated(self):
        run = BacktestRun.objects.create(
            requested_by=self.owner,
            strategy=self.strategy,
            instrument=self.instrument,
            date_range={"start": "2025-01-01", "end": "2025-01-31"},
            initial_capital=Decimal("10000"),
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/v1/backtests/{run.pk}/").status_code, 404)

        self.client.force_authenticate(self.owner)
        invalid = self.client.post("/api/v1/backtests/", {
            "strategy": self.strategy.pk,
            "instrument": self.instrument.pk,
            "start_date": "2025-02-01",
            "end_date": "2025-01-01",
            "initial_capital": "0",
        }, format="json")
        self.assertEqual(invalid.status_code, 400)
