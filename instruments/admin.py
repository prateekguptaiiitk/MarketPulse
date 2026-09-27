from django.contrib import admin

from .models import Instrument, PriceBar


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "exchange", "sector", "is_active")
    list_filter = ("exchange", "sector", "is_active")
    search_fields = ("symbol", "name")


@admin.register(PriceBar)
class PriceBarAdmin(admin.ModelAdmin):
    list_display = ("instrument", "interval", "timestamp", "close", "volume")
    list_filter = ("interval", "instrument")
