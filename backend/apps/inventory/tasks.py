"""
Celery tasks for inventory management.
"""

import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_reorder_levels():
    """
    Scan all active inventory items and flag those at or below their
    reorder point.  Creates alert events and optionally triggers
    automated requisition generation.

    Scheduled daily at 06:00 UTC via Celery Beat.
    """
    from apps.accounts.models import Organization
    from apps.analytics.models import AlertEvent, AlertRule
    from apps.inventory.models import InventoryItem

    organizations = Organization.objects.filter(is_active=True)
    total_alerts = 0

    for org in organizations:
        items = InventoryItem.objects.filter(
            organization=org, is_active=True
        ).select_related("preferred_supplier")

        low_stock_items = [item for item in items if item.is_below_reorder_point]

        if not low_stock_items:
            continue

        # Find an active low-stock alert rule for this org
        rule = AlertRule.objects.filter(
            organization=org,
            rule_type=AlertRule.RuleType.LOW_STOCK,
            is_active=True,
        ).first()

        for item in low_stock_items:
            if rule:
                # Avoid duplicate alerts for the same item within 24h
                recent_alert = AlertEvent.objects.filter(
                    rule=rule,
                    related_object_id=item.id,
                    created_at__gte=timezone.now() - timezone.timedelta(hours=24),
                ).exists()

                if not recent_alert:
                    AlertEvent.objects.create(
                        organization=org,
                        rule=rule,
                        severity=AlertEvent.Severity.WARNING,
                        title=f"Low Stock: {item.sku}",
                        message=(
                            f"Item '{item.name}' (SKU: {item.sku}) has "
                            f"{item.total_stock} units, which is at or below "
                            f"the reorder point of {item.reorder_point}."
                        ),
                        related_object_type="inventory_item",
                        related_object_id=item.id,
                    )
                    total_alerts += 1

        logger.info(
            "Org %s: %d items below reorder point, %d alerts created",
            org.name,
            len(low_stock_items),
            total_alerts,
        )

    return {"low_stock_items_found": total_alerts}


@shared_task
def recalculate_inventory_values():
    """
    Recalculate the total inventory value for each organization
    and store as a metric snapshot.
    """
    from django.db.models import F, Sum
    from apps.accounts.models import Organization
    from apps.analytics.models import DashboardMetricSnapshot
    from apps.inventory.models import StockLevel

    today = timezone.now().date()
    organizations = Organization.objects.filter(is_active=True)

    for org in organizations:
        total = StockLevel.objects.filter(
            item__organization=org
        ).aggregate(
            value=Sum(F("quantity") * F("item__unit_cost"))
        )["value"] or Decimal("0")

        DashboardMetricSnapshot.objects.update_or_create(
            organization=org,
            metric_name="inventory_value",
            snapshot_date=today,
            defaults={"value": total},
        )

    logger.info("Inventory values recalculated for %d organizations", organizations.count())


@shared_task
def generate_stock_movement_report(organization_id: str, days: int = 30):
    """
    Generate a stock movement summary for the specified organization
    over the last N days.  Returns data suitable for charting.
    """
    from apps.accounts.models import Organization
    from apps.inventory.models import StockLevel

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.error("Organization %s not found", organization_id)
        return None

    cutoff = timezone.now() - timezone.timedelta(days=days)
    movements = (
        StockLevel.objects.filter(
            item__organization=org,
            updated_at__gte=cutoff,
        )
        .select_related("item", "warehouse")
        .order_by("-updated_at")
    )

    results = []
    for sl in movements[:500]:
        results.append({
            "item_sku": sl.item.sku,
            "item_name": sl.item.name,
            "warehouse": sl.warehouse.code,
            "quantity": float(sl.quantity),
            "reserved": float(sl.reserved_quantity),
            "available": float(sl.available_quantity),
            "updated_at": sl.updated_at.isoformat(),
        })

    logger.info(
        "Stock movement report generated for %s: %d records",
        org.name,
        len(results),
    )
    return results
