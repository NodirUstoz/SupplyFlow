"""
Inventory views.
"""

from django.db.models import F, Sum
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import InventoryItem, StockLevel, Warehouse
from .serializers import (
    InventoryItemDetailSerializer,
    InventoryItemListSerializer,
    StockLevelSerializer,
    WarehouseSerializer,
)


class WarehouseViewSet(viewsets.ModelViewSet):
    """CRUD for warehouses."""

    serializer_class = WarehouseSerializer
    filterset_fields = ["is_active", "country"]
    search_fields = ["name", "code", "city"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Warehouse.objects.select_related("manager", "organization")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=True, methods=["get"])
    def stock(self, request, pk=None):
        """List all stock levels at this warehouse."""
        warehouse = self.get_object()
        stock = warehouse.stock_levels.select_related("item").all()
        serializer = StockLevelSerializer(stock, many=True)
        return Response(serializer.data)


class InventoryItemViewSet(viewsets.ModelViewSet):
    """CRUD for inventory items."""

    filterset_fields = ["category", "is_active", "preferred_supplier"]
    search_fields = ["sku", "name", "description"]
    ordering_fields = ["name", "sku", "unit_cost", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = InventoryItem.objects.select_related(
            "preferred_supplier", "organization"
        ).prefetch_related("stock_levels", "stock_levels__warehouse")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return InventoryItemListSerializer
        return InventoryItemDetailSerializer

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """List items that are at or below their reorder point."""
        qs = self.get_queryset().filter(is_active=True)
        low_stock_items = []
        for item in qs:
            if item.is_below_reorder_point:
                low_stock_items.append(item)
        serializer = InventoryItemListSerializer(low_stock_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def adjust_stock(self, request, pk=None):
        """Adjust stock level at a specific warehouse."""
        item = self.get_object()
        warehouse_id = request.data.get("warehouse_id")
        quantity_change = request.data.get("quantity_change")
        reason = request.data.get("reason", "")

        if warehouse_id is None or quantity_change is None:
            return Response(
                {"detail": "warehouse_id and quantity_change are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            return Response(
                {"detail": "Warehouse not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        stock_level, created = StockLevel.objects.get_or_create(
            item=item, warehouse=warehouse
        )
        from decimal import Decimal, InvalidOperation
        try:
            change = Decimal(str(quantity_change))
        except (InvalidOperation, ValueError):
            return Response(
                {"detail": "Invalid quantity_change value."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_qty = stock_level.quantity + change
        if new_qty < 0:
            return Response(
                {"detail": "Resulting quantity cannot be negative."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_level.quantity = new_qty
        stock_level.save(update_fields=["quantity", "updated_at"])

        serializer = StockLevelSerializer(stock_level)
        return Response(serializer.data)


class StockLevelViewSet(viewsets.ModelViewSet):
    """CRUD for stock levels."""

    serializer_class = StockLevelSerializer
    filterset_fields = ["item", "warehouse"]
    ordering_fields = ["quantity", "updated_at"]

    def get_queryset(self):
        user = self.request.user
        qs = StockLevel.objects.select_related("item", "warehouse")
        if not user.is_superuser:
            qs = qs.filter(item__organization=user.organization)
        return qs
