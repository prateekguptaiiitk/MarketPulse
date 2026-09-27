"""Focused tests for email account creation and JWT authentication."""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from accounts.factories import UserFactory


class AccountAuthenticationTests(TestCase):
    def test_factory_boy_user_factory_uses_the_custom_manager(self):
        user = UserFactory(password="Factory-test-password-456!")
        self.assertTrue(user.check_password("Factory-test-password-456!"))

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

    def test_api_errors_use_common_envelope_and_openapi_pages_are_served(self):
        unauthenticated = self.client.get("/api/v1/instruments/")
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.data["error"]["status"], 401)
        self.assertIn("message", unauthenticated.data["error"])

        schema = self.client.get("/api/schema/")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("openapi", schema.data)
        swagger = self.client.get("/api/schema/swagger-ui/")
        self.assertEqual(swagger.status_code, 200)
