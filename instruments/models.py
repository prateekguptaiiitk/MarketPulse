"""Tradable instruments and indexed historical market bars."""
from django.db import models

'''
    NOTE: In Django, fields that use auto_now_add=True or auto_now=True are automatically set to editable=False
    behind the scenes. By default, the Django admin panel completely hides non-editable fields from the object
    creation and modification forms to prevent users from trying to change values that are handled automatically
    by the system
'''
class Instrument(models.Model):
    symbol = models.CharField(max_length=32, unique=True)
    exchange = models.CharField(max_length=16, blank=True)
    name = models.CharField(max_length=160)
    sector = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]
        indexes = [models.Index(fields=["exchange", "symbol"], name="instr_exchange_symbol_idx")]

    def __str__(self) -> str:
        return self.symbol


class PriceBar(models.Model):
    class Interval(models.TextChoices):
        ONE_MINUTE = "1m", "1 minute"
        FIVE_MINUTES = "5m", "5 minutes"
        ONE_DAY = "1d", "1 day"

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="price_bars")
    timestamp = models.DateTimeField()
    open = models.DecimalField(max_digits=18, decimal_places=6)
    high = models.DecimalField(max_digits=18, decimal_places=6)
    low = models.DecimalField(max_digits=18, decimal_places=6)
    close = models.DecimalField(max_digits=18, decimal_places=6)
    volume = models.PositiveBigIntegerField(default=0)
    interval = models.CharField(max_length=2, choices=Interval.choices, default=Interval.ONE_DAY)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [models.UniqueConstraint(fields=["instrument", "timestamp", "interval"], name="uniq_instrument_bar_interval")]
        indexes = [
            models.Index(fields=["instrument", "timestamp"], name="price_instr_timestamp_idx"),
            models.Index(fields=["instrument", "interval", "timestamp"], name="price_instr_int_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.instrument.symbol} {self.interval} {self.timestamp.isoformat()}"
