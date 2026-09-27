"""Alert condition, cooldown, delivery, and API isolation tests."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from alerts.models import Alert, AlertTriggerLog
from alerts.services import evaluate_alert, trigger_alert
from alerts.tasks import evaluate_active_alerts
from instruments.models import Instrument, PriceBar
from strategies.models import Strategy


class AlertServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alerts@example.com", "Strong-example-pass-734!")
        self.instrument = Instrument.objects.create(symbol="ALT", name="Alert Equity")
        PriceBar.objects.create(
            instrument=self.instrument,
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            open=Decimal("110"), high=Decimal("112"), low=Decimal("109"), close=Decimal("111"), volume=1000,
        )

    def test_alert_evaluates_latest_price_condition(self):
        alert = Alert.objects.create(
            user=self.user,
            instrument=self.instrument,
            name="Price breakout",
            condition={"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 100}]},
        )
        result = evaluate_alert(alert)
        self.assertTrue(result["triggered"])
        self.assertEqual(result["price"], "111.000000")

    @patch("alerts.services.deliver_alert")
    def test_trigger_is_logged_and_respects_cooldown(self, deliver):
        alert = Alert.objects.create(
            user=self.user,
            instrument=self.instrument,
            name="Price breakout",
            condition={"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 100}]},
        )

        self.assertTrue(trigger_alert(alert.pk))
        self.assertFalse(trigger_alert(alert.pk))
        deliver.assert_called_once()
        self.assertEqual(AlertTriggerLog.objects.count(), 1)
        log = AlertTriggerLog.objects.get()
        self.assertEqual(log.delivery_status, AlertTriggerLog.DeliveryStatus.SENT)
        self.assertEqual(log.price, Decimal("111.000000"))

    @patch("alerts.services.deliver_alert", side_effect=RuntimeError("mail unavailable"))
    def test_delivery_failures_are_retained_in_trigger_history(self, _deliver):
        alert = Alert.objects.create(
            user=self.user,
            instrument=self.instrument,
            name="Price breakout",
            condition={"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 100}]},
        )
        self.assertTrue(trigger_alert(alert.pk))
        log = AlertTriggerLog.objects.get(alert=alert)
        self.assertEqual(log.delivery_status, AlertTriggerLog.DeliveryStatus.FAILED)
        self.assertIn("mail unavailable", log.delivery_error)

    @patch("alerts.tasks.trigger_alert", side_effect=[True, False])
    def test_beat_task_reports_evaluation_counts(self, trigger):
        for index in range(2):
            instrument = Instrument.objects.create(symbol=f"TASK{index}", name="Task Equity")
            Alert.objects.create(
                user=self.user,
                instrument=instrument,
                name="Task alert",
                condition={"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 1}]},
            )
        result = evaluate_active_alerts.apply().result
        self.assertEqual(result, {"evaluated": 2, "triggered": 1, "failed": 0})
        self.assertEqual(trigger.call_count, 2)


class AlertApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.com", "Strong-example-pass-734!")
        self.other = User.objects.create_user("other@example.com", "Strong-example-pass-734!")
        self.instrument = Instrument.objects.create(symbol="APIALT", name="API Alert Equity")
        self.strategy = Strategy.objects.create(
            user=self.owner,
            name="RSI entry",
            rules=[{"indicator": "RSI", "condition": "less_than", "value": 30}],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_alert_create_and_history_are_user_scoped(self):
        response = self.client.post("/api/v1/alerts/", {
            "name": "RSI warning",
            "instrument": self.instrument.pk,
            "strategy": self.strategy.pk,
            "notification_channel": "email",
            "cooldown_minutes": 10,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        alert_id = response.data["id"]

        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/v1/alerts/{alert_id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/alerts/{alert_id}/history/").status_code, 404)

    def test_alert_requires_conditions_or_strategy_and_secure_webhook(self):
        invalid = self.client.post("/api/v1/alerts/", {
            "name": "Empty", "instrument": self.instrument.pk,
        }, format="json")
        self.assertEqual(invalid.status_code, 400)

        invalid_webhook = self.client.post("/api/v1/alerts/", {
            "name": "Webhook", "instrument": self.instrument.pk,
            "condition": {"logic": "AND", "rules": [{"indicator": "PRICE", "condition": "greater_than", "value": 100}]},
            "notification_channel": "webhook", "webhook_url": "https://127.0.0.1/hook",
        }, format="json")
        self.assertEqual(invalid_webhook.status_code, 400)
