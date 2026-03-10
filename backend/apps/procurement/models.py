"""
Procurement models: PurchaseRequisition, PurchaseOrder, PurchaseOrderLine,
ApprovalWorkflow.
"""

import uuid

from django.conf import settings
from django.db import models


class PurchaseRequisition(models.Model):
    """Internal request to purchase goods or services."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CONVERTED = "converted", "Converted to PO"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="requisitions",
    )
    requisition_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requisitions",
    )
    department = models.CharField(max_length=100, blank=True)
    estimated_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    required_date = models.DateField(null=True, blank=True)
    justification = models.TextField(blank=True)
    suggested_supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requisitions",
    )
    purchase_order = models.OneToOneField(
        "PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_requisition",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requisition_number} - {self.title}"


class PurchaseOrder(models.Model):
    """Purchase order sent to a supplier."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent to Supplier"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    actual_lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    payment_terms = models.CharField(max_length=50, blank=True)
    shipping_address = models.TextField(blank=True)
    billing_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_purchase_orders",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name}"

    def recalculate_totals(self):
        """Recalculate subtotal and total from line items."""
        from django.db.models import Sum, F

        agg = self.lines.aggregate(
            subtotal=Sum(F("quantity") * F("unit_price"))
        )
        self.subtotal = agg["subtotal"] or 0
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
        self.save(update_fields=["subtotal", "total_amount", "updated_at"])


class PurchaseOrderLine(models.Model):
    """Individual line item on a purchase order."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    item_code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, default="EA", help_text="Unit of measure")
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    line_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="po_lines",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["line_number"]
        unique_together = [("purchase_order", "line_number")]

    def __str__(self):
        return f"PO {self.purchase_order.po_number} Line {self.line_number}"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class ApprovalWorkflow(models.Model):
    """Tracks approval steps for purchase orders and requisitions."""

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned for Revision"

    class TargetType(models.TextChoices):
        REQUISITION = "requisition", "Purchase Requisition"
        PURCHASE_ORDER = "purchase_order", "Purchase Order"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="approval_workflows",
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField(help_text="ID of the requisition or PO")
    step_order = models.PositiveIntegerField(default=1)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_tasks",
    )
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING)
    comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = [("target_type", "target_id", "step_order")]

    def __str__(self):
        return (
            f"{self.target_type} approval step {self.step_order} "
            f"- {self.get_decision_display()}"
        )
