"""
Quality serializers.
"""

from rest_framework import serializers

from .models import DefectReport, InspectionItem, QualityInspection


class DefectReportSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.CharField(
        source="reported_by.full_name", read_only=True, default=None
    )
    severity_display = serializers.CharField(
        source="get_severity_display", read_only=True
    )

    class Meta:
        model = DefectReport
        fields = [
            "id", "inspection", "inspection_item", "defect_code", "title",
            "description", "severity", "severity_display", "quantity_affected",
            "root_cause", "disposition", "corrective_action", "image",
            "reported_by", "reported_by_name", "resolved", "resolved_at",
            "created_at",
        ]
        read_only_fields = ["id", "reported_by", "created_at"]

    def create(self, validated_data):
        validated_data["reported_by"] = self.context["request"].user
        return super().create(validated_data)


class InspectionItemSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source="get_result_display", read_only=True)
    defects = DefectReportSerializer(many=True, read_only=True)

    class Meta:
        model = InspectionItem
        fields = [
            "id", "inspection", "inventory_item", "item_code", "description",
            "quantity_inspected", "quantity_accepted", "quantity_rejected",
            "result", "result_display", "criteria", "measurements",
            "notes", "defects",
        ]
        read_only_fields = ["id"]


class QualityInspectionListSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(
        source="inspector.full_name", read_only=True, default=None
    )
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True, default=None
    )
    defect_rate = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = QualityInspection
        fields = [
            "id", "inspection_number", "inspection_type", "status",
            "supplier_name", "inspector_name", "inspection_date",
            "overall_score", "sample_size", "defects_found",
            "defect_rate", "item_count", "created_at",
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class QualityInspectionDetailSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(
        source="inspector.full_name", read_only=True, default=None
    )
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True, default=None
    )
    po_number = serializers.CharField(
        source="purchase_order.po_number", read_only=True, default=None
    )
    shipment_number = serializers.CharField(
        source="shipment.shipment_number", read_only=True, default=None
    )
    items = InspectionItemSerializer(many=True, read_only=True)
    defect_reports = DefectReportSerializer(many=True, read_only=True)
    defect_rate = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )

    class Meta:
        model = QualityInspection
        fields = [
            "id", "organization", "inspection_number", "inspection_type",
            "status", "purchase_order", "po_number", "shipment",
            "shipment_number", "supplier", "supplier_name",
            "inspector", "inspector_name", "inspection_date",
            "overall_score", "sample_size", "defects_found", "defect_rate",
            "notes", "corrective_action", "items", "defect_reports",
            "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "inspector", "created_at", "updated_at",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["inspector"] = user
        return super().create(validated_data)
