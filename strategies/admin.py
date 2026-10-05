from django.contrib import admin

from .models import Strategy


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "logic", "exit_logic", "is_active", "created_at")
    list_filter = ("logic", "exit_logic", "is_active", "created_at")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at", "updated_at")
