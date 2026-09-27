"""Persistent asynchronous backtest runs and computed result summaries."""
from django.conf import settings
from django.db import models

from instruments.models import Instrument, PriceBar
from strategies.models import Strategy


class BacktestRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    strategy = models.ForeignKey(Strategy, on_delete=models.PROTECT, related_name="backtest_runs")
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name="backtest_runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="backtest_runs")
    date_range = models.JSONField(help_text="Inclusive start and end dates in ISO format.")
    interval = models.CharField(max_length=2, choices=PriceBar.Interval.choices, default=PriceBar.Interval.ONE_DAY)
    initial_capital = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    task_id = models.CharField(max_length=255, blank=True)
    results = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["requested_by", "status"], name="backtest_user_status_idx")]

    def __str__(self) -> str:
        return f"Backtest {self.pk}: {self.instrument.symbol} ({self.status})"
