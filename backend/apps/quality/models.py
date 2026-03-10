"""
Quality models: QualityInspection, InspectionItem, DefectReport.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class QualityInspection(models.Model):
    """Inspection performed on received goods."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        CONDITIONAL = "conditional", "Conditional Pass"

    class InspectionType(models.TextChoices):
        INCOMING = "incoming", "Incoming Goods"
        IN_PROCESS = "in_process", "In-Process"
        FINAL = "final", "Final Inspection"
        PERIODIC = "periodic", "Periodic Audit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspection_number = models.CharField(max_length=50, unique=True)
    inspection_type = models.CharField(
        max_length=20, choices=InspectionType.choices, default=InspectionType.INCOMING
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    shipment = models.ForeignKey(
        "shipments.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="inspections",
    )
    inspection_date = models.DateField()
    overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall quality score 0-100",
    )
    sample_size = models.PositiveIntegerField(default=1)
    defects_found = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-inspection_date"]

    def __str__(self):
        return f"{self.inspection_number} - {self.get_status_display()}"

    @property
    def defect_rate(self):
        if self.sample_size == 0:
            return 0
        return round(self.defects_found / self.sample_size * 100, 2)


class InspectionItem(models.Model):
    """Individual item checked during an inspection."""

    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        WARNING = "warning", "Warning"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(
        QualityInspection, on_delete=models.CASCADE, related_name="items"
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    item_code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    quantity_inspected = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_accepted = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.PASS)
    criteria = models.TextField(blank=True, help_text="Inspection criteria applied")
    measurements = models.JSONField(
        default=dict, blank=True,
        help_text="Key-value pairs of measurement data",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["item_code"]

    def __str__(self):
        return f"{self.item_code} - {self.get_result_display()}"


class DefectReport(models.Model):
    """Detailed defect record linked to an inspection."""

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        MAJOR = "major", "Major"
        MINOR = "minor", "Minor"
        COSMETIC = "cosmetic", "Cosmetic"

    class DispositionAction(models.TextChoices):
        RETURN_TO_SUPPLIER = "return", "Return to Supplier"
        REWORK = "rework", "Rework"
        SCRAP = "scrap", "Scrap"
        USE_AS_IS = "use_as_is", "Use As Is"
        HOLD = "hold", "Hold for Decision"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(
        QualityInspection, on_delete=models.CASCADE, related_name="defect_reports"
    )
    inspection_item = models.ForeignKey(
        InspectionItem, on_delete=models.CASCADE, null=True, blank=True,
        related_name="defects",
    )
    defect_code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=Severity.choices)
    quantity_affected = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    root_cause = models.TextField(blank=True)
    disposition = models.CharField(
        max_length=20, choices=DispositionAction.choices, default=DispositionAction.HOLD
    )
    corrective_action = models.TextField(blank=True)
    image = models.ImageField(upload_to="defects/", blank=True, null=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.defect_code} - {self.title} ({self.get_severity_display()})"
