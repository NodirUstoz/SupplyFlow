"""
Forecasting serializers.
"""

from rest_framework import serializers

from .models import DemandForecast, ForecastAccuracy, ForecastConfiguration


class ForecastConfigurationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )

    class Meta:
        model = ForecastConfiguration
        fields = [
            "id", "organization", "organization_name", "default_method",
            "lookback_days", "forecast_horizon_days",
            "safety_stock_multiplier", "auto_reorder_enabled",
            "updated_by", "updated_at",
        ]
        read_only_fields = ["id", "organization", "updated_by", "updated_at"]

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)


class DemandForecastSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    item_name = serializers.CharField(source="inventory_item.name", read_only=True)

    class Meta:
        model = DemandForecast
        fields = [
            "id", "organization", "inventory_item", "item_sku", "item_name",
            "forecast_date", "predicted_quantity",
            "confidence_lower", "confidence_upper",
            "method", "status", "generated_at",
        ]
        read_only_fields = [
            "id", "organization", "generated_at",
        ]


class ForecastAccuracySerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source="inventory_item.sku", read_only=True)
    item_name = serializers.CharField(source="inventory_item.name", read_only=True)

    class Meta:
        model = ForecastAccuracy
        fields = [
            "id", "organization", "inventory_item", "item_sku", "item_name",
            "forecast_date", "predicted_quantity", "actual_quantity",
            "absolute_error", "percentage_error", "method", "evaluated_at",
        ]
        read_only_fields = fields


class ForecastSummarySerializer(serializers.Serializer):
    """Read-only summary of forecast health for a given item."""

    inventory_item_id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    avg_predicted_quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    forecast_count = serializers.IntegerField()
    avg_accuracy_pct = serializers.DecimalField(
        max_digits=8, decimal_places=2, allow_null=True
    )
    recommended_reorder_qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, allow_null=True,
    )
