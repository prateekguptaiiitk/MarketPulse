"""User-scoped alert CRUD and trigger history API."""
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from alerts.models import Alert
from alerts.serializers import AlertSerializer, AlertTriggerLogSerializer


class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ["name", "instrument__symbol"]
    ordering_fields = ["created_at", "name", "last_triggered_at"]

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).select_related("instrument", "strategy")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None, version=None, **kwargs):
        alert = self.get_object()
        logs = alert.trigger_logs.all()
        page = self.paginate_queryset(logs)
        serializer = AlertTriggerLogSerializer(page or logs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
