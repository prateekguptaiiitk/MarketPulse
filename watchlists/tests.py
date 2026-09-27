"""API tests for watchlist ownership and item validation."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from instruments.models import Instrument
from watchlists.models import Watchlist, WatchlistItem

class WatchlistApiTests(TestCase):
    def test_watchlists_are_scoped_to_the_authenticated_user(self):
        owner = User.objects.create_user("owner@example.com", "Strong-example-pass-734!")
        stranger = User.objects.create_user("stranger@example.com", "Strong-example-pass-734!")
        watchlist = Watchlist.objects.create(user=owner, name="Long term")
        client = APIClient()
        client.force_authenticate(stranger)

        self.assertEqual(client.get("/api/v1/watchlists/").data["count"], 0)
        self.assertEqual(client.get(f"/api/v1/watchlists/{watchlist.pk}/").status_code, 404)
        self.assertEqual(client.patch(f"/api/v1/watchlists/{watchlist.pk}/", {"name": "stolen"}).status_code, 404)

    def test_items_can_only_be_added_once_and_inactive_instruments_are_rejected(self):
        user = User.objects.create_user("owner@example.com", "Strong-example-pass-734!")
        watchlist = Watchlist.objects.create(user=user, name="Growth")
        instrument = Instrument.objects.create(symbol="ABC", name="ABC Corp")
        client = APIClient()
        client.force_authenticate(user)
        url = f"/api/v1/watchlists/{watchlist.pk}/items/"

        self.assertEqual(client.post(url, {"instrument": instrument.pk}).status_code, 201)
        self.assertEqual(client.post(url, {"instrument": instrument.pk}).status_code, 400)
        inactive = Instrument.objects.create(symbol="XYZ", name="XYZ Corp", is_active=False)
        response = client.post(url, {"instrument": inactive.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WatchlistItem.objects.filter(watchlist=watchlist).count(), 1)
