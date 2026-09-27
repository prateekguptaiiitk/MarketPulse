"""Celery task wrapper for long-running backtest computations."""
import logging

from celery import shared_task
from django.utils import timezone

from .engine import run_backtest_for_run
from .models import BacktestRun

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="backtesting.run_backtest")
def run_backtest(self, run_id: int):
    """Execute a run and persist either computed results or a safe error message."""
    try:
        run = BacktestRun.objects.get(pk=run_id)
    except BacktestRun.DoesNotExist:
        logger.warning("Backtest run %s was deleted before execution", run_id)
        return {"status": "missing"}

    run.status = BacktestRun.Status.RUNNING
    run.started_at = timezone.now()
    run.task_id = self.request.id or run.task_id
    run.save(update_fields=["status", "started_at", "task_id"])
    try:
        run.results = run_backtest_for_run(run.id)
        run.status = BacktestRun.Status.COMPLETED
    except Exception as exc:  # Persist task failure so clients can poll without Celery result access.
        logger.exception("Backtest run %s failed", run_id)
        run.status = BacktestRun.Status.FAILED
        run.results = {"error": str(exc)}
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "results", "completed_at"])
    return {"run_id": run.id, "status": run.status}
