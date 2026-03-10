"""
Analytics services: snapshot generation and alert evaluation.

Called by Celery tasks to compute daily metric snapshots and fire alerts
when KPI targets are breached.
"""

import logging
from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, F, Sum

from apps.accounts.models import Organization
from apps.inventory.models import InventoryItem, StockLevel
from apps.procurement.models import ApprovalWorkflow, PurchaseOrder
from apps.shipments.models import Shipment
from apps.suppliers.models import Supplier

from .models import AlertEvent, AlertRule, DashboardMetricSnapshot, KPITarget

logger = logging.getLogger(__name__)


class SnapshotService:
    """Generate daily metric snapshots for every active organization."""

    @staticmethod
    def generate_all(snapshot_date: date = None):
        if snapshot_date is None:
            snapshot_date = date.today()

        organizations = Organization.objects.filter(is_active=True)
        total_created = 0

        for org in organizations:
            created = SnapshotService._generate_for_org(org, snapshot_date)
            total_created += created

        logger.info(
            "Generated %d metric snapshots for %d organizations on %s",
            total_created,
            organizations.count(),
            snapshot_date,
        )
        return total_created

    @staticmethod
    def _generate_for_org(org, snapshot_date: date) -> int:
        metrics = {}

        # Total PO value (open orders)
        open_statuses = [
            PurchaseOrder.Status.DRAFT,
            PurchaseOrder.Status.PENDING_APPROVAL,
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.SENT,
            PurchaseOrder.Status.ACKNOWLEDGED,
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
        ]
        total_po = PurchaseOrder.objects.filter(
            organization=org, status__in=open_statuses
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        metrics["total_po_value"] = total_po

        # Open PO count
        metrics["open_po_count"] = Decimal(
            PurchaseOrder.objects.filter(
                organization=org, status__in=open_statuses
            ).count()
        )

        # Inventory value
        inv_val = StockLevel.objects.filter(
            item__organization=org
        ).aggregate(
            total=Sum(F("quantity") * F("item__unit_cost"))
        )["total"] or Decimal("0")
        metrics["inventory_value"] = inv_val

        # Low stock count
        items = InventoryItem.objects.filter(organization=org, is_active=True)
        low = sum(1 for i in items if i.is_below_reorder_point)
        metrics["low_stock_count"] = Decimal(low)

        # Active shipments
        active_statuses = [
            Shipment.Status.PICKED_UP,
            Shipment.Status.IN_TRANSIT,
            Shipment.Status.CUSTOMS,
            Shipment.Status.OUT_FOR_DELIVERY,
        ]
        metrics["active_shipments"] = Decimal(
            Shipment.objects.filter(
                organization=org, status__in=active_statuses
            ).count()
        )

        # On-time delivery rate
        delivered = Shipment.objects.filter(
            organization=org,
            status=Shipment.Status.DELIVERED,
            actual_arrival__isnull=False,
            estimated_arrival__isnull=False,
        )
        if delivered.exists():
            on_time = delivered.filter(actual_arrival__lte=F("estimated_arrival")).count()
            rate = Decimal(str(round(on_time / delivered.count() * 100, 2)))
        else:
            rate = Decimal("0")
        metrics["on_time_delivery"] = rate

        # Average supplier score
        avg = Supplier.objects.filter(
            organization=org, status="active"
        ).aggregate(avg=Avg("overall_score"))["avg"]
        metrics["supplier_avg_score"] = Decimal(str(round(avg, 2))) if avg else Decimal("0")

        # Average lead time
        avg_lt = PurchaseOrder.objects.filter(
            organization=org,
            actual_lead_time_days__isnull=False,
        ).aggregate(avg=Avg("actual_lead_time_days"))["avg"]
        metrics["avg_lead_time"] = Decimal(str(round(avg_lt, 2))) if avg_lt else Decimal("0")

        # Pending approvals
        pending = ApprovalWorkflow.objects.filter(
            organization=org,
            decision=ApprovalWorkflow.Decision.PENDING,
        ).count()
        metrics["pending_approvals"] = Decimal(pending)

        created = 0
        for metric_name, value in metrics.items():
            _, was_created = DashboardMetricSnapshot.objects.update_or_create(
                organization=org,
                metric_name=metric_name,
                snapshot_date=snapshot_date,
                defaults={"value": value},
            )
            if was_created:
                created += 1
        return created


class AlertService:
    """Evaluate alert rules and create events for breached KPI targets."""

    @staticmethod
    def evaluate_all():
        """Check all active KPI targets and fire alerts for breaches."""
        targets = KPITarget.objects.filter(is_active=True).select_related("organization")
        fired = 0

        for target in targets:
            latest = DashboardMetricSnapshot.objects.filter(
                organization=target.organization,
                metric_name=target.metric_name,
            ).order_by("-snapshot_date").first()

            if latest is None:
                continue

            if target.is_breached(latest.value):
                # Find matching alert rule
                rules = AlertRule.objects.filter(
                    organization=target.organization,
                    is_active=True,
                )
                for rule in rules:
                    AlertEvent.objects.create(
                        organization=target.organization,
                        rule=rule,
                        severity=AlertEvent.Severity.WARNING,
                        title=f"KPI Target Breached: {target.get_metric_name_display()}",
                        message=(
                            f"Current value {latest.value} does not meet target "
                            f"{target.target_value} ({target.get_direction_display()})."
                        ),
                        related_object_type="kpi_target",
                        related_object_id=target.id,
                    )
                    fired += 1

        logger.info("Alert evaluation complete: %d alerts fired", fired)
        return fired
