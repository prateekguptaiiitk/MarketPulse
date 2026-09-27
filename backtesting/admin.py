from django.contrib import admin

from .models import BacktestRun


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "strategy", "instrument", "status", "requested_by", "created_at")
    list_filter = ("status", "interval")
    search_fields = ("instrument__symbol", "strategy__name", "requested_by__email", "task_id")
    readonly_fields = ("results", "task_id", "created_at", "started_at", "completed_at")
