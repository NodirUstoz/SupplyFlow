"""
Inventory serializers.
"""

from rest_framework import serializers

from .models import InventoryItem, StockLevel, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source="manager.full_name", read_only=True, default=None)
    utilization = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            "id", "organization", "name", "code", "address", "city",
            "state", "country", "postal_code", "latitude", "longitude",
            "capacity", "manager", "manager_name", "utilization",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def get_utilization(self, obj):
        if not obj.capacity:
            return None
        from django.db.models import Sum
        total = obj.stock_levels.aggregate(total=Sum("quantity"))["total"] or 0
        return round(float(total) / obj.capacity * 100, 1)

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user.organization
        return super().create(validated_data)


class StockLevelSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    available_quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True
    )

    class Meta:
        model = StockLevel
        fields = [
            "id", "item", "item_sku", "item_name", "warehouse",
            "warehouse_name", "warehouse_code", "quantity",
            "reserved_quantity", "available_quantity",
            "last_counted_at", "last_received_at", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class InventoryItemListSerializer(serializers.ModelSerializer):
    total_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True
    )
    is_below_reorder_point = serializers.BooleanField(read_only=True)
    supplier_name = serializers.CharField(
        source="preferred_supplier.name", read_only=True, default=None
    )

    class Meta:
        model = InventoryItem
        fields = [
            "id", "sku", "name", "category", "unit_of_measure",
            "unit_cost", "currency", "reorder_point", "total_stock",
            "is_below_reorder_point", "preferred_supplier",
            "supplier_name", "is_active", "created_at",
        ]


class InventoryItemDetailSerializer(serializers.ModelSerializer):
    stock_levels = StockLevelSerializer(many=True, read_only=True)
    total_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, read_only=True
    )
    is_below_reorder_point = serializers.BooleanField(read_only=True)
    supplier_name = serializers.CharField(
        source="preferred_supplier.name", read_only=True, default=None
    )

    class Meta:
        model = InventoryItem
        fields = [
            "id", "organization", "sku", "name", "description", "category",
            "unit_of_measure", "unit_cost", "currency", "weight_kg",
            "dimensions", "reorder_point", "reorder_quantity",
            "lead_time_days", "preferred_supplier", "supplier_name",
            "is_active", "image", "stock_levels", "total_stock",
            "is_below_reorder_point", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user.organization
        return super().create(validated_data)
