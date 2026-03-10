"""
Inventory business-logic services.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import InventoryItem, StockLevel, Warehouse

logger = logging.getLogger(__name__)


class StockService:
    """Service layer for stock management operations."""

    @staticmethod
    @transaction.atomic
    def receive_stock(
        item: InventoryItem,
        warehouse: Warehouse,
        quantity: Decimal,
        reference: str = "",
    ) -> StockLevel:
        """
        Add stock to a warehouse after receiving a delivery.

        Updates the stock level and records the receive timestamp.
        """
        if quantity <= 0:
            raise ValueError("Receive quantity must be positive.")

        stock, _ = StockLevel.objects.select_for_update().get_or_create(
            item=item, warehouse=warehouse
        )
        stock.quantity += quantity
        stock.last_received_at = timezone.now()
        stock.save(update_fields=["quantity", "last_received_at", "updated_at"])

        logger.info(
            "Received %.3f of %s at %s (ref: %s). New qty: %.3f",
            quantity, item.sku, warehouse.code, reference, stock.quantity,
        )
        return stock

    @staticmethod
    @transaction.atomic
    def reserve_stock(
        item: InventoryItem,
        warehouse: Warehouse,
        quantity: Decimal,
    ) -> StockLevel:
        """
        Reserve stock for a pending order.

        Raises ValueError if insufficient available quantity.
        """
        stock = StockLevel.objects.select_for_update().get(
            item=item, warehouse=warehouse
        )

        if stock.available_quantity < quantity:
            raise ValueError(
                f"Insufficient stock: {stock.available_quantity} available, "
                f"{quantity} requested."
            )

        stock.reserved_quantity += quantity
        stock.save(update_fields=["reserved_quantity", "updated_at"])

        logger.info(
            "Reserved %.3f of %s at %s. Reserved now: %.3f",
            quantity, item.sku, warehouse.code, stock.reserved_quantity,
        )
        return stock

    @staticmethod
    @transaction.atomic
    def release_reservation(
        item: InventoryItem,
        warehouse: Warehouse,
        quantity: Decimal,
    ) -> StockLevel:
        """Release previously reserved stock (e.g. order cancelled)."""
        stock = StockLevel.objects.select_for_update().get(
            item=item, warehouse=warehouse
        )
        stock.reserved_quantity = max(
            Decimal("0"), stock.reserved_quantity - quantity
        )
        stock.save(update_fields=["reserved_quantity", "updated_at"])

        logger.info(
            "Released %.3f reservation of %s at %s",
            quantity, item.sku, warehouse.code,
        )
        return stock

    @staticmethod
    @transaction.atomic
    def transfer_stock(
        item: InventoryItem,
        from_warehouse: Warehouse,
        to_warehouse: Warehouse,
        quantity: Decimal,
    ) -> tuple:
        """
        Move stock between warehouses.

        Returns (source_stock_level, dest_stock_level).
        """
        if from_warehouse == to_warehouse:
            raise ValueError("Source and destination warehouses must differ.")
        if quantity <= 0:
            raise ValueError("Transfer quantity must be positive.")

        source = StockLevel.objects.select_for_update().get(
            item=item, warehouse=from_warehouse
        )
        if source.available_quantity < quantity:
            raise ValueError(
                f"Insufficient available stock at {from_warehouse.code}: "
                f"{source.available_quantity}"
            )

        source.quantity -= quantity
        source.save(update_fields=["quantity", "updated_at"])

        dest, _ = StockLevel.objects.select_for_update().get_or_create(
            item=item, warehouse=to_warehouse
        )
        dest.quantity += quantity
        dest.last_received_at = timezone.now()
        dest.save(update_fields=["quantity", "last_received_at", "updated_at"])

        logger.info(
            "Transferred %.3f of %s from %s to %s",
            quantity, item.sku, from_warehouse.code, to_warehouse.code,
        )
        return source, dest

    @staticmethod
    @transaction.atomic
    def cycle_count(
        item: InventoryItem,
        warehouse: Warehouse,
        counted_quantity: Decimal,
    ) -> StockLevel:
        """
        Record a physical inventory count.  Adjusts the quantity to match
        the counted amount.
        """
        stock, _ = StockLevel.objects.select_for_update().get_or_create(
            item=item, warehouse=warehouse
        )
        old_qty = stock.quantity
        stock.quantity = counted_quantity
        stock.last_counted_at = timezone.now()
        stock.save(update_fields=["quantity", "last_counted_at", "updated_at"])

        variance = counted_quantity - old_qty
        if variance != 0:
            logger.warning(
                "Cycle count variance for %s at %s: system=%.3f, counted=%.3f, diff=%.3f",
                item.sku, warehouse.code, old_qty, counted_quantity, variance,
            )
        return stock

    @staticmethod
    def get_items_needing_reorder(organization) -> list:
        """Return all active items below their reorder point."""
        items = InventoryItem.objects.filter(
            organization=organization, is_active=True
        ).select_related("preferred_supplier")
        return [item for item in items if item.is_below_reorder_point]
