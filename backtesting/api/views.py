"""Authenticated API to submit and poll backtest runs."""
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from backtesting.models import BacktestRun
from backtesting.serializers import BacktestCreateSerializer, BacktestRunSerializer
from backtesting.tasks import run_backtest


class BacktestRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Create async jobs and expose only runs belonging to the current user."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BacktestRun.objects.filter(requested_by=self.request.user).select_related("strategy", "instrument")

    def get_serializer_class(self):
        if self.action == "create":
            return BacktestCreateSerializer
        return BacktestRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = serializer.save()

        def enqueue():
            try:
                result = run_backtest.delay(run.pk)
                run.task_id = result.id or ""
                run.save(update_fields=["task_id"])
            except Exception as exc:
                run.status = BacktestRun.Status.FAILED
                run.results = {"error": f"Could not enqueue backtest: {exc}"}
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "results", "completed_at"])

        transaction.on_commit(enqueue)
        response_data = BacktestRunSerializer(run, context=self.get_serializer_context()).data
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_202_ACCEPTED, headers=headers)
