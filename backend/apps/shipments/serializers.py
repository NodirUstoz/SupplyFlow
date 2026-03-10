"""
Shipment serializers.
"""

from rest_framework import serializers

from .models import Carrier, Shipment, ShipmentItem, ShipmentTracking


class CarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrier
        fields = [
            "id", "name", "code", "contact_email", "contact_phone",
            "website", "tracking_url_template", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentTracking
        fields = [
            "id", "shipment", "status", "location", "latitude", "longitude",
            "description", "event_time", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ShipmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentItem
        fields = [
            "id", "shipment", "po_line", "item_code", "description",
            "quantity", "unit", "weight_kg",
        ]
        read_only_fields = ["id"]


class ShipmentListSerializer(serializers.ModelSerializer):
    carrier_name = serializers.CharField(source="carrier.name", read_only=True, default=None)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True, default=None)
    item_count = serializers.SerializerMethodField()
    tracking_url = serializers.CharField(read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id", "shipment_number", "shipment_type", "status",
            "carrier_name", "tracking_number", "tracking_url",
            "po_number", "origin_address", "destination_address",
            "estimated_departure", "estimated_arrival",
            "actual_departure", "actual_arrival",
            "shipping_cost", "currency", "item_count", "created_at",
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class ShipmentDetailSerializer(serializers.ModelSerializer):
    carrier_name = serializers.CharField(source="carrier.name", read_only=True, default=None)
    carrier_detail = CarrierSerializer(source="carrier", read_only=True)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True, default=None)
    items = ShipmentItemSerializer(many=True, read_only=True)
    tracking_events = ShipmentTrackingSerializer(many=True, read_only=True)
    tracking_url = serializers.CharField(read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id", "organization", "shipment_number", "shipment_type",
            "purchase_order", "po_number", "carrier", "carrier_name",
            "carrier_detail", "tracking_number", "tracking_url",
            "status", "origin_address", "destination_address",
            "origin_latitude", "origin_longitude",
            "destination_latitude", "destination_longitude",
            "estimated_departure", "actual_departure",
            "estimated_arrival", "actual_arrival",
            "weight_kg", "shipping_cost", "currency", "notes",
            "items", "tracking_events",
            "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "created_by", "created_at", "updated_at",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["created_by"] = user
        return super().create(validated_data)
