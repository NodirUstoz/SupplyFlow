"""
Admin configuration for shipments app.
"""

from django.contrib import admin

from .models import Carrier, Shipment, ShipmentItem, ShipmentTracking


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0
    fields = ("item_code", "description", "quantity", "unit", "weight_kg")


class ShipmentTrackingInline(admin.TabularInline):
    model = ShipmentTracking
    extra = 0
    fields = ("status", "location", "event_time", "description")
    ordering = ("-event_time",)


@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "shipment_number", "shipment_type", "status", "carrier",
        "tracking_number", "estimated_arrival", "actual_arrival",
        "shipping_cost",
    )
    list_filter = ("status", "shipment_type", "carrier", "organization")
    search_fields = ("shipment_number", "tracking_number")
    inlines = [ShipmentItemInline, ShipmentTrackingInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(ShipmentItem)
class ShipmentItemAdmin(admin.ModelAdmin):
    list_display = ("item_code", "shipment", "quantity", "unit", "weight_kg")
    search_fields = ("item_code", "description")


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = ("shipment", "status", "location", "event_time")
    list_filter = ("status",)
    ordering = ("-event_time",)
