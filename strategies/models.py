"""User-owned, JSON-defined entry and exit strategies."""
from django.conf import settings
from django.db import models


class Strategy(models.Model):
    class Logic(models.TextChoices):
        AND = "AND", "All conditions must match"
        OR = "OR", "Any condition may match"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="strategies")
    name = models.CharField(max_length=120)
    rules = models.JSONField(default=list, help_text="Entry conditions; each item names an indicator, condition, and value.")
    logic = models.CharField(max_length=3, choices=Logic.choices, default=Logic.AND)
    exit_rules = models.JSONField(default=list, help_text="Exit conditions evaluated independently from entry conditions.")
    exit_logic = models.CharField(max_length=3, choices=Logic.choices, default=Logic.OR)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="uniq_strategy_name_per_user")]
        '''
            Django generates the plural from the model name `Strategy`, and its default pluralization 
            produces "Strategys" in django admin panel, therefore we define verbose plural name instead
        '''
        verbose_name_plural = "Strategies"

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"
