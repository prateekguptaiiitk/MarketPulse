"""JWT authentication middleware for browser and API WebSocket clients."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_access_token(encoded_token):
    """Validate an access token and load its active account asynchronously."""
    try:
        token = AccessToken(encoded_token)
        user_id = token[api_settings.USER_ID_CLAIM]
        return get_user_model().objects.get(pk=user_id, is_active=True)
    except (TokenError, get_user_model().DoesNotExist, KeyError, TypeError, ValueError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """Add a user to the scope from an Authorization header or short-lived query token."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin1")
        token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
        if not token:
            query = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="ignore"))
            token = (query.get("token") or [""])[0]
        user = await _user_from_access_token(token) if token else AnonymousUser()
        return await self.inner(dict(scope, user=user), receive, send)
