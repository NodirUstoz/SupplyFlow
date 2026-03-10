"""
Supplier models: Supplier, SupplierContact, SupplierRating, Contract.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Supplier(models.Model):
    """Primary supplier entity."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        PENDING = "pending", "Pending Approval"
        BLOCKED = "blocked", "Blocked"

    class Category(models.TextChoices):
        RAW_MATERIALS = "raw_materials", "Raw Materials"
        COMPONENTS = "components", "Components"
        PACKAGING = "packaging", "Packaging"
        LOGISTICS = "logistics", "Logistics"
        SERVICES = "services", "Services"
        EQUIPMENT = "equipment", "Equipment"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="suppliers",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, help_text="Unique supplier code")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    tax_id = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="US")
    postal_code = models.CharField(max_length=20, blank=True)
    payment_terms = models.CharField(
        max_length=50, default="Net 30",
        help_text="e.g. Net 30, Net 60, COD",
    )
    currency = models.CharField(max_length=3, default="USD")
    lead_time_days = models.PositiveIntegerField(
        default=7, help_text="Average lead time in days"
    )
    notes = models.TextField(blank=True)
    overall_score = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Composite performance score 0-10",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_suppliers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("organization", "code")]

    def __str__(self):
        return f"{self.name} ({self.code})"


class SupplierContact(models.Model):
    """Contact person at a supplier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="contacts"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.supplier.name}"


class SupplierRating(models.Model):
    """Periodic rating for a supplier across key dimensions."""

    class Dimension(models.TextChoices):
        QUALITY = "quality", "Quality"
        DELIVERY = "delivery", "Delivery Reliability"
        PRICE = "price", "Price Competitiveness"
        COMMUNICATION = "communication", "Communication"
        FLEXIBILITY = "flexibility", "Flexibility"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="ratings"
    )
    dimension = models.CharField(max_length=20, choices=Dimension.choices)
    score = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    period_start = models.DateField()
    period_end = models.DateField()
    comments = models.TextField(blank=True)
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end"]
        unique_together = [("supplier", "dimension", "period_start", "period_end")]

    def __str__(self):
        return f"{self.supplier.name} - {self.dimension} ({self.score})"


class Contract(models.Model):
    """Supplier contract / agreement."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        TERMINATED = "terminated", "Terminated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="contracts"
    )
    contract_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    end_date = models.DateField()
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    terms = models.TextField(blank=True)
    document = models.FileField(upload_to="contracts/", blank=True, null=True)
    auto_renew = models.BooleanField(default=False)
    renewal_notice_days = models.PositiveIntegerField(
        default=30, help_text="Days before expiry to send renewal notice"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.contract_number} - {self.title}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.end_date < timezone.now().date()
