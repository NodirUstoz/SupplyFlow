"""
Analytics models: DashboardMetricSnapshot, KPITarget, AlertRule, AlertEvent.

These models store pre-computed aggregates and alert configurations so that
dashboard queries remain fast regardless of transaction volume.
"""

import uuid

from django.conf import settings
from django.db import models


class DashboardMetricSnapshot(models.Model):
    """
    Point-in-time snapshot of a key metric, stored daily.

    Used to power trend charts on the dashboard without re-aggregating
    raw data on every page load.
    """

    class MetricName(models.TextChoices):
        TOTAL_PO_VALUE = "total_po_value", "Total PO Value"
        OPEN_PO_COUNT = "open_po_count", "Open PO Count"
        INVENTORY_VALUE = "inventory_value", "Inventory Value"
        LOW_STOCK_COUNT = "low_stock_count", "Low Stock Item Count"
        ON_TIME_DELIVERY_RATE = "on_time_delivery", "On-Time Delivery %"
        SUPPLIER_AVG_SCORE = "supplier_avg_score", "Average Supplier Score"
        ACTIVE_SHIPMENTS = "active_shipments", "Active Shipments"
        DEFECT_RATE = "defect_rate", "Defect Rate %"
        AVG_LEAD_TIME = "avg_lead_time", "Average Lead Time (days)"
        PENDING_APPROVALS = "pending_approvals", "Pending Approvals"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="metric_snapshots",
    )
    metric_name = models.CharField(max_length=30, choices=MetricName.choices)
    value = models.DecimalField(max_digits=18, decimal_places=4)
    snapshot_date = models.DateField()
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Optional breakdown details (e.g. by category, by warehouse)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-snapshot_date"]
        unique_together = [("organization", "metric_name", "snapshot_date")]

    def __str__(self):
        return f"{self.metric_name} = {self.value} ({self.snapshot_date})"


class KPITarget(models.Model):
    """
    Organizational target for a metric (e.g. on-time delivery >= 95%).

    Used by the alert engine to detect breaches.
    """

    class Direction(models.TextChoices):
        ABOVE = "above", "Above (value >= target)"
        BELOW = "below", "Below (value <= target)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="kpi_targets",
    )
    metric_name = models.CharField(
        max_length=30,
        choices=DashboardMetricSnapshot.MetricName.choices,
    )
    target_value = models.DecimalField(max_digits=18, decimal_places=4)
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.ABOVE)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["metric_name"]
        unique_together = [("organization", "metric_name")]

    def __str__(self):
        symbol = ">=" if self.direction == self.Direction.ABOVE else "<="
        return f"{self.metric_name} {symbol} {self.target_value}"

    def is_breached(self, current_value):
        """Return True if the current value violates this target."""
        if self.direction == self.Direction.ABOVE:
            return current_value < self.target_value
        return current_value > self.target_value


class AlertRule(models.Model):
    """
    Configurable rule that triggers notifications when conditions are met.

    Examples:
      - Inventory item below reorder point
      - Supplier score drops below 5.0
      - Shipment overdue by more than 2 days
    """

    class RuleType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        OVERDUE_SHIPMENT = "overdue_shipment", "Overdue Shipment"
        PO_OVER_BUDGET = "po_over_budget", "PO Over Budget"
        SUPPLIER_SCORE_DROP = "supplier_score_drop", "Supplier Score Drop"
        CONTRACT_EXPIRING = "contract_expiring", "Contract Expiring"
        QUALITY_FAILURE = "quality_failure", "Quality Inspection Failed"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WEBHOOK = "webhook", "Webhook"
        IN_APP = "in_app", "In-App Notification"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=30, choices=RuleType.choices)
    is_active = models.BooleanField(default=True)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.IN_APP)
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="alert_subscriptions",
    )
    config = models.JSONField(
        default=dict, blank=True,
        help_text="Rule-specific thresholds, e.g. {'days_before_expiry': 30}",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class AlertEvent(models.Model):
    """
    Record of a triggered alert.
    """

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="alert_events",
    )
    rule = models.ForeignKey(
        AlertRule, on_delete=models.CASCADE, related_name="events"
    )
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.title}"
