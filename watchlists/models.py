"""Per-user watchlists and their instrument membership."""
from django.conf import settings
from django.db import models

from instruments.models import Instrument


class Watchlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlists")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="uniq_watchlist_name_per_user")]

    def __str__(self) -> str:
        return f"{self.user}: {self.name}"


class WatchlistItem(models.Model):
    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name="items")
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="watchlist_items")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [models.UniqueConstraint(fields=["watchlist", "instrument"], name="uniq_instrument_per_watchlist")]
        indexes = [models.Index(fields=["watchlist", "added_at"], name="watchlist_added_idx")]

    def __str__(self) -> str:
        return f"{self.instrument.symbol} in {self.watchlist.name}"
