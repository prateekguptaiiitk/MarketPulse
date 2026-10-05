"""User-scoped strategy CRUD API."""
from rest_framework import permissions, viewsets

from strategies.models import Strategy
from strategies.serializers import StrategySerializer


class StrategyViewSet(viewsets.ModelViewSet):
    """Only expose strategies owned by the current authenticated user."""

    serializer_class = StrategySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]

    def get_queryset(self):
        '''
            getattr : built-in function used to dynamically retrieve the value of an object's attribute or
            method using its string name
            getattr(object, name, default)
        '''
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return Strategy.objects.none()
        return Strategy.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
