from django.contrib import admin

from .models import Alert, AlertTriggerLog


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "instrument",
        "user",
        "is_active",
        "notification_channel",
        "last_triggered_at",
    )
    list_filter = ("is_active", "notification_channel", "interval")
    search_fields = ("name", "instrument__symbol", "user__email")
    readonly_fields = ("last_triggered_at", "created_at", "updated_at")


@admin.register(AlertTriggerLog)
class AlertTriggerLogAdmin(admin.ModelAdmin):
    list_display = ("alert", "triggered_at", "price", "delivery_status")
    list_filter = ("delivery_status", "triggered_at")
    search_fields = (
        "alert__name",
        "alert__instrument__symbol",
        "alert__user__email",
    )
    readonly_fields = (
        "alert",
        "triggered_at",
        "price",
        "condition_results",
        "delivery_status",
        "delivery_error",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False