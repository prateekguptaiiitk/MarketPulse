"""API tests for instrument access control and price history pagination."""
from datetime import datetime, timezone
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from instruments.models import Instrument, PriceBar

class InstrumentApiTests(TestCase):
    def test_instruments_are_readable_by_members_but_writes_require_staff(self):
        regular = User.objects.create_user("member@example.com", "Strong-example-pass-734!")
        client = APIClient()
        client.force_authenticate(regular)
        self.assertEqual(client.get("/api/v1/instruments/").status_code, 200)
        response = client.post("/api/v1/instruments/", {"symbol": "ABC", "name": "ABC Corp"})
        self.assertEqual(response.status_code, 403)

        staff = User.objects.create_user("staff@example.com", "Strong-example-pass-734!", is_staff=True)
        client.force_authenticate(staff)
        response = client.post("/api/v1/instruments/", {"symbol": "ABC", "name": "ABC Corp"})
        self.assertEqual(response.status_code, 201)

    def test_price_history_is_cursor_paginated(self):
        user = User.objects.create_user("member@example.com", "Strong-example-pass-734!")
        instrument = Instrument.objects.create(symbol="ABC", name="ABC Corp")
        for day in range(3):
            PriceBar.objects.create(
                instrument=instrument,
                timestamp=datetime(2025, 1, day + 1, tzinfo=timezone.utc),
                open=10, high=11, low=9, close=10, volume=100,
            )
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(f"/api/v1/instruments/{instrument.pk}/prices/?page_size=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertTrue(response.data["next"])


class DemoSeedCommandTests(TestCase):
    def test_demo_seed_is_idempotent(self):
        output = StringIO()
        call_command("seed_demo_data", days=3, stdout=output)
        call_command("seed_demo_data", days=3, stdout=output)

        self.assertEqual(Instrument.objects.count(), 12)
        self.assertEqual(PriceBar.objects.count(), 12 * 3)
        self.assertIn("deterministic daily bars", output.getvalue())
