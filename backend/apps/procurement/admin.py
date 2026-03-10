"""
Admin configuration for procurement app.
"""

from django.contrib import admin

from .models import ApprovalWorkflow, PurchaseOrder, PurchaseOrderLine, PurchaseRequisition


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = (
        "requisition_number", "title", "status", "priority",
        "requested_by", "estimated_total", "required_date",
    )
    list_filter = ("status", "priority", "department")
    search_fields = ("requisition_number", "title")
    readonly_fields = ("created_at", "updated_at")


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0
    fields = (
        "line_number", "item_code", "description", "quantity",
        "unit", "unit_price", "line_total", "quantity_received",
    )
    readonly_fields = ("line_total",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "po_number", "supplier", "status", "order_date",
        "expected_delivery_date", "total_amount", "currency",
    )
    list_filter = ("status", "currency")
    search_fields = ("po_number", "supplier__name")
    inlines = [PurchaseOrderLineInline]
    readonly_fields = ("subtotal", "total_amount", "created_at", "updated_at")


@admin.register(ApprovalWorkflow)
class ApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "target_type", "target_id", "step_order", "approver",
        "decision", "decided_at",
    )
    list_filter = ("target_type", "decision")
