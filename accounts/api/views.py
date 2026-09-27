"""Versioned authentication endpoints."""
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from drf_spectacular.utils import extend_schema

from accounts.serializers import RefreshTokenSerializer, RegisterSerializer


class RegisterView(generics.CreateAPIView):
    """Register an account; credentials are never returned."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


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
