"""
Shipment models: Shipment, ShipmentItem, ShipmentTracking, Carrier.
"""

import uuid

from django.conf import settings
from django.db import models


class Carrier(models.Model):
    """Shipping carrier (e.g. FedEx, DHL, Maersk)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    tracking_url_template = models.URLField(
        blank=True,
        help_text="Use {tracking_number} as placeholder, e.g. https://track.example.com/{tracking_number}",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_tracking_url(self, tracking_number: str) -> str:
        if self.tracking_url_template:
            return self.tracking_url_template.replace("{tracking_number}", tracking_number)
        return ""


class Shipment(models.Model):
    """A shipment moving goods from supplier to warehouse."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PICKED_UP = "picked_up", "Picked Up"
        IN_TRANSIT = "in_transit", "In Transit"
        CUSTOMS = "customs", "In Customs"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Delivery Failed"
        RETURNED = "returned", "Returned"

    class ShipmentType(models.TextChoices):
        INBOUND = "inbound", "Inbound (from Supplier)"
        OUTBOUND = "outbound", "Outbound (to Customer)"
        TRANSFER = "transfer", "Inter-warehouse Transfer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="shipments",
    )
    shipment_number = models.CharField(max_length=50, unique=True)
    shipment_type = models.CharField(
        max_length=20, choices=ShipmentType.choices, default=ShipmentType.INBOUND
    )
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments",
    )
    carrier = models.ForeignKey(
        Carrier, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments"
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    origin_address = models.TextField(blank=True)
    destination_address = models.TextField(blank=True)
    origin_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    origin_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    destination_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    destination_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    estimated_departure = models.DateTimeField(null=True, blank=True)
    actual_departure = models.DateTimeField(null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_shipments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.shipment_number} ({self.get_status_display()})"

    @property
    def tracking_url(self):
        if self.carrier and self.tracking_number:
            return self.carrier.get_tracking_url(self.tracking_number)
        return ""


class ShipmentItem(models.Model):
    """Individual item within a shipment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name="items"
    )
    po_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    item_code = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, default="EA")
    weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["item_code"]

    def __str__(self):
        return f"{self.item_code} x {self.quantity}"


class ShipmentTracking(models.Model):
    """Status updates / milestones for a shipment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name="tracking_events"
    )
    status = models.CharField(max_length=20, choices=Shipment.Status.choices)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField(blank=True)
    event_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_time"]

    def __str__(self):
        return f"{self.shipment.shipment_number} - {self.status} at {self.event_time}"
