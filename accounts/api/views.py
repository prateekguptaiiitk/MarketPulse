"""Versioned authentication endpoints."""
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema

from accounts.serializers import RefreshTokenSerializer, RegisterSerializer

'''
    `RegisterView` uses `generics.CreateAPIView` because registration is a standard **create** operation.
     DRF handles the usual flow: pass request data to `RegisterSerializer`, validate it, call its `create()` method,
     and return a response. The view only needs to specify the serializer and allow unauthenticated access.
'''
class RegisterView(generics.CreateAPIView):
    """Register an account; credentials are never returned."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]



'''
    `LogoutView` uses `APIView` because logging out here is a custom action: it reads a refresh token, blacklists it,
     and returns HTTP 204. There’s no model object to create or retrieve, so `CreateAPIView` wouldn’t provide a useful
     shortcut.
'''
class LogoutView(APIView):
    """Blacklist a submitted refresh token to end its session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=RefreshTokenSerializer, responses={204: None})
    def post(self, request, *args, **kwargs):
        token = request.data.get("refresh")
        if not token:
            raise ValidationError({"refresh": "Refresh token is required."})
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            raise ValidationError({"refresh": "Invalid or expired refresh token."})
        return Response(status=status.HTTP_204_NO_CONTENT)
