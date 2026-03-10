"""
Admin configuration for inventory app.
"""

from django.contrib import admin

from .models import InventoryItem, StockLevel, Warehouse


class StockLevelInline(admin.TabularInline):
    model = StockLevel
    extra = 0
    fields = ("warehouse", "quantity", "reserved_quantity", "last_counted_at")
    readonly_fields = ("last_counted_at",)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = (
        "name", "code", "city", "country", "capacity",
        "manager", "is_active",
    )
    list_filter = ("is_active", "country", "organization")
    search_fields = ("name", "code", "city")
    readonly_fields = ("created_at", "updated_at")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "sku", "name", "category", "unit_cost", "currency",
        "reorder_point", "lead_time_days", "is_active",
    )
    list_filter = ("category", "is_active", "organization")
    search_fields = ("sku", "name", "description")
    inlines = [StockLevelInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = (
        "item", "warehouse", "quantity", "reserved_quantity",
        "last_counted_at", "updated_at",
    )
    list_filter = ("warehouse",)
    search_fields = ("item__sku", "item__name")
