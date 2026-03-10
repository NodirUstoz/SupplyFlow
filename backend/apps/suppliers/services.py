"""
Supplier business-logic services.
"""

import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Contract, Supplier, SupplierRating

logger = logging.getLogger(__name__)


class SupplierService:
    """Service layer for supplier operations."""

    @staticmethod
    @transaction.atomic
    def onboard_supplier(organization, data: dict, created_by) -> Supplier:
        """
        Create a new supplier with status PENDING and generate a unique code.
        """
        code = SupplierService._generate_supplier_code(organization, data.get("name", ""))
        supplier = Supplier.objects.create(
            organization=organization,
            name=data["name"],
            code=code,
            category=data.get("category", Supplier.Category.OTHER),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            website=data.get("website", ""),
            country=data.get("country", "US"),
            payment_terms=data.get("payment_terms", "Net 30"),
            created_by=created_by,
            status=Supplier.Status.PENDING,
        )
        logger.info("Supplier %s onboarded (pending approval)", supplier.code)
        return supplier

    @staticmethod
    def _generate_supplier_code(organization, name: str) -> str:
        """Generate a supplier code from the first 3 letters + sequence."""
        prefix = "".join(c for c in name.upper() if c.isalpha())[:3]
        if len(prefix) < 3:
            prefix = prefix.ljust(3, "X")

        existing = Supplier.objects.filter(
            organization=organization,
            code__startswith=f"SUP-{prefix}",
        ).count()

        return f"SUP-{prefix}-{existing + 1:04d}"

    @staticmethod
    @transaction.atomic
    def activate_supplier(supplier: Supplier) -> Supplier:
        """Approve and activate a pending supplier."""
        if supplier.status not in (Supplier.Status.PENDING, Supplier.Status.INACTIVE):
            raise ValueError(f"Cannot activate supplier with status '{supplier.status}'.")
        supplier.status = Supplier.Status.ACTIVE
        supplier.save(update_fields=["status", "updated_at"])
        logger.info("Supplier %s activated", supplier.code)
        return supplier

    @staticmethod
    @transaction.atomic
    def block_supplier(supplier: Supplier, reason: str = "") -> Supplier:
        """Block a supplier, preventing new purchase orders."""
        supplier.status = Supplier.Status.BLOCKED
        if reason:
            supplier.notes = f"{supplier.notes}\n[BLOCKED] {reason}".strip()
        supplier.save(update_fields=["status", "notes", "updated_at"])
        logger.warning("Supplier %s blocked: %s", supplier.code, reason)
        return supplier

    @staticmethod
    def get_performance_summary(supplier: Supplier) -> dict:
        """
        Build a comprehensive performance summary for a supplier.
        """
        from apps.procurement.models import PurchaseOrder

        # Rating breakdown
        rating_summary = {}
        for dim_choice in SupplierRating.Dimension.choices:
            dim_value = dim_choice[0]
            latest = (
                SupplierRating.objects.filter(
                    supplier=supplier, dimension=dim_value
                )
                .order_by("-period_end")
                .first()
            )
            historical_avg = SupplierRating.objects.filter(
                supplier=supplier, dimension=dim_value
            ).aggregate(avg=Avg("score"))["avg"]

            rating_summary[dim_value] = {
                "latest_score": float(latest.score) if latest else None,
                "historical_avg": round(float(historical_avg), 2) if historical_avg else None,
                "latest_period": str(latest.period_end) if latest else None,
            }

        # PO statistics
        po_qs = PurchaseOrder.objects.filter(supplier=supplier)
        total_orders = po_qs.count()
        total_value = po_qs.aggregate(
            total=sum_field("total_amount")
        )["total"] or Decimal("0")
        avg_lead_time = po_qs.filter(
            actual_lead_time_days__isnull=False
        ).aggregate(avg=Avg("actual_lead_time_days"))["avg"]

        # On-time delivery rate
        delivered = po_qs.filter(
            actual_delivery_date__isnull=False,
            expected_delivery_date__isnull=False,
        )
        if delivered.exists():
            on_time = delivered.filter(
                actual_delivery_date__lte=models_f("expected_delivery_date")
            ).count()
            on_time_rate = round(on_time / delivered.count() * 100, 2)
        else:
            on_time_rate = None

        # Active contracts
        active_contracts = Contract.objects.filter(
            supplier=supplier, status=Contract.Status.ACTIVE
        ).count()

        return {
            "supplier_id": str(supplier.id),
            "supplier_name": supplier.name,
            "overall_score": float(supplier.overall_score),
            "rating_breakdown": rating_summary,
            "total_orders": total_orders,
            "total_order_value": float(total_value),
            "avg_lead_time_days": round(avg_lead_time, 1) if avg_lead_time else None,
            "on_time_delivery_rate": on_time_rate,
            "active_contracts": active_contracts,
        }


def sum_field(field_name):
    from django.db.models import Sum
    return Sum(field_name)


def models_f(field_name):
    from django.db.models import F
    return F(field_name)
