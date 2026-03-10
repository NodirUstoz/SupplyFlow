"""
Inventory models: InventoryItem, StockLevel, Warehouse.
"""

import uuid

from django.conf import settings
from django.db import models


class Warehouse(models.Model):
    """Physical warehouse / storage location."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="warehouses",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="US")
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    capacity = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total storage capacity in units"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_warehouses",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class InventoryItem(models.Model):
    """Master catalog item that can be stored in warehouses."""

    class Category(models.TextChoices):
        RAW_MATERIAL = "raw_material", "Raw Material"
        COMPONENT = "component", "Component"
        FINISHED_GOOD = "finished_good", "Finished Good"
        PACKAGING = "packaging", "Packaging"
        MRO = "mro", "Maintenance/Repair/Operations"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="inventory_items",
    )
    sku = models.CharField(max_length=50, unique=True, help_text="Stock Keeping Unit")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    unit_of_measure = models.CharField(max_length=20, default="EA")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, default="USD")
    weight_kg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True, help_text="LxWxH in cm")
    reorder_point = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Quantity threshold that triggers a reorder",
    )
    reorder_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Default order quantity when reordering",
    )
    lead_time_days = models.PositiveIntegerField(
        default=7, help_text="Expected days to replenish"
    )
    preferred_supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplied_items",
    )
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to="inventory/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def total_stock(self):
        """Total quantity across all warehouses."""
        from django.db.models import Sum
        result = self.stock_levels.aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def is_below_reorder_point(self):
        return self.total_stock <= self.reorder_point


class StockLevel(models.Model):
    """Quantity of an item at a specific warehouse."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="stock_levels"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stock_levels"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reserved_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text="Quantity reserved for pending orders",
    )
    last_counted_at = models.DateTimeField(null=True, blank=True)
    last_received_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("item", "warehouse")]
        ordering = ["item__sku"]

    def __str__(self):
        return f"{self.item.sku} @ {self.warehouse.code}: {self.quantity}"

    @property
    def available_quantity(self):
        return max(self.quantity - self.reserved_quantity, 0)
