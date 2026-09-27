"""Price and strategy alerts plus durable notification trigger history."""
from django.conf import settings
from django.db import models

from instruments.models import Instrument, PriceBar
from strategies.models import Strategy


class Alert(models.Model):
    class NotificationChannel(models.TextChoices):
        EMAIL = "email", "Email"
        WEBHOOK = "webhook", "Webhook"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts")
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="alerts")
    strategy = models.ForeignKey(Strategy, on_delete=models.SET_NULL, null=True, blank=True, related_name="alerts")
    name = models.CharField(max_length=120)
    condition = models.JSONField(default=dict, blank=True, help_text="Rule set used when strategy is not supplied.")
    interval = models.CharField(max_length=2, choices=PriceBar.Interval.choices, default=PriceBar.Interval.ONE_DAY)
    is_active = models.BooleanField(default=True, db_index=True)
    notification_channel = models.CharField(max_length=10, choices=NotificationChannel.choices, default=NotificationChannel.EMAIL)
    webhook_url = models.URLField(blank=True)
    cooldown_minutes = models.PositiveSmallIntegerField(default=5)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "instrument"], name="alert_active_instr_idx")]

    def __str__(self) -> str:
        return f"{self.name} ({self.instrument.symbol})"


class AlertTriggerLog(models.Model):
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="trigger_logs")
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    condition_results = models.JSONField(default=dict)
    delivery_status = models.CharField(max_length=10, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivery_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-triggered_at"]
        indexes = [models.Index(fields=["alert", "triggered_at"], name="alert_log_time_idx")]

    def __str__(self) -> str:
        return f"Alert {self.alert_id} triggered at {self.triggered_at}"
