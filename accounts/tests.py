"""Focused tests for email account creation and JWT authentication."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User


class AccountAuthenticationTests(TestCase):
    def test_registration_normalizes_email_and_hashes_password(self):
        response = self.client.post("/api/v1/auth/register/", {"email": "Trader@Example.com", "password": "Strong-example-pass-734!"})

        self.assertEqual(response.status_code, 201)
        user = User.objects.get()
        self.assertEqual(user.email, "trader@example.com")
        self.assertTrue(user.check_password("Strong-example-pass-734!"))
        self.assertNotIn("password", response.data)

    def test_login_issues_jwt_and_logout_blacklists_refresh_token(self):
        User.objects.create_user("trader@example.com", "Strong-example-pass-734!")
        client = APIClient()
        response = client.post("/api/v1/auth/login/", {"email": "trader@example.com", "password": "Strong-example-pass-734!"})

        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        logout = client.post("/api/v1/auth/logout/", {"refresh": response.data["refresh"]})
        self.assertEqual(logout.status_code, 204)
