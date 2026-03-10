"""
Procurement serializers.
"""

from rest_framework import serializers

from .models import ApprovalWorkflow, PurchaseOrder, PurchaseOrderLine, PurchaseRequisition


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    supplier_name = serializers.CharField(source="suggested_supplier.name", read_only=True, default=None)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id", "organization", "requisition_number", "title", "description",
            "status", "priority", "requested_by", "requested_by_name",
            "department", "estimated_total", "currency", "required_date",
            "justification", "suggested_supplier", "supplier_name",
            "purchase_order", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "requested_by", "purchase_order",
            "created_at", "updated_at",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["requested_by"] = user
        return super().create(validated_data)


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id", "purchase_order", "line_number", "item_code", "description",
            "quantity", "unit", "unit_price", "line_total", "quantity_received",
            "inventory_item", "notes",
        ]
        read_only_fields = ["id", "line_total"]


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "supplier", "supplier_name", "status",
            "order_date", "expected_delivery_date", "total_amount", "currency",
            "created_by_name", "line_count", "created_at",
        ]

    def get_line_count(self, obj):
        return obj.lines.count()


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True, default=None)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "organization", "po_number", "supplier", "supplier_name",
            "status", "order_date", "expected_delivery_date",
            "actual_delivery_date", "actual_lead_time_days",
            "subtotal", "tax_amount", "shipping_cost", "total_amount",
            "currency", "payment_terms", "shipping_address", "billing_address",
            "notes", "internal_notes", "lines",
            "created_by", "created_by_name", "approved_by", "approved_by_name",
            "approved_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "subtotal", "total_amount",
            "created_by", "approved_by", "approved_at",
            "created_at", "updated_at",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["created_by"] = user
        return super().create(validated_data)


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a PO with nested line items."""

    lines = PurchaseOrderLineSerializer(many=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "po_number", "supplier", "expected_delivery_date",
            "tax_amount", "shipping_cost", "currency", "payment_terms",
            "shipping_address", "billing_address", "notes", "internal_notes",
            "lines",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["created_by"] = user
        po = PurchaseOrder.objects.create(**validated_data)
        for idx, line_data in enumerate(lines_data, start=1):
            line_data.pop("purchase_order", None)
            PurchaseOrderLine.objects.create(
                purchase_order=po, line_number=idx, **line_data
            )
        po.recalculate_totals()
        return po


class ApprovalWorkflowSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)

    class Meta:
        model = ApprovalWorkflow
        fields = [
            "id", "organization", "target_type", "target_id", "step_order",
            "approver", "approver_name", "decision", "comments",
            "decided_at", "created_at",
        ]
        read_only_fields = ["id", "organization", "decided_at", "created_at"]

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user.organization
        return super().create(validated_data)


class ApprovalActionSerializer(serializers.Serializer):
    """Serializer for submitting an approval decision."""

    decision = serializers.ChoiceField(choices=ApprovalWorkflow.Decision.choices)
    comments = serializers.CharField(required=False, allow_blank=True)
