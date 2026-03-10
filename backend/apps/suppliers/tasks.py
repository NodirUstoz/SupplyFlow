"""
Celery tasks for supplier management.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.db.models import Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def compute_supplier_scores():
    """
    Recalculate the overall_score for every active supplier based on
    their latest ratings across all dimensions.

    Scheduled weekly (Monday 03:00 UTC) via Celery Beat.
    """
    from apps.suppliers.models import Supplier, SupplierRating

    suppliers = Supplier.objects.filter(status=Supplier.Status.ACTIVE)
    updated = 0

    for supplier in suppliers:
        # Average of the most-recent score in each dimension
        dimension_scores = []
        for dim_choice in SupplierRating.Dimension.choices:
            dim_value = dim_choice[0]
            latest = (
                SupplierRating.objects.filter(
                    supplier=supplier, dimension=dim_value
                )
                .order_by("-period_end")
                .values_list("score", flat=True)
                .first()
            )
            if latest is not None:
                dimension_scores.append(float(latest))

        if dimension_scores:
            new_score = Decimal(str(
                round(sum(dimension_scores) / len(dimension_scores), 2)
            ))
        else:
            new_score = Decimal("0")

        if supplier.overall_score != new_score:
            supplier.overall_score = new_score
            supplier.save(update_fields=["overall_score", "updated_at"])
            updated += 1

    logger.info("Supplier scores recalculated: %d updated", updated)
    return {"suppliers_updated": updated}


@shared_task
def check_expiring_contracts(days_ahead: int = 30):
    """
    Find supplier contracts expiring within the next N days and create
    alert events for each.
    """
    from apps.analytics.models import AlertEvent, AlertRule
    from apps.suppliers.models import Contract

    cutoff = timezone.now().date() + timedelta(days=days_ahead)
    expiring = Contract.objects.filter(
        status=Contract.Status.ACTIVE,
        end_date__lte=cutoff,
        end_date__gte=timezone.now().date(),
    ).select_related("supplier", "supplier__organization")

    alerts_created = 0
    for contract in expiring:
        org = contract.supplier.organization
        rule = AlertRule.objects.filter(
            organization=org,
            rule_type=AlertRule.RuleType.CONTRACT_EXPIRING,
            is_active=True,
        ).first()

        if not rule:
            continue

        # Check for recent duplicate alert
        recent = AlertEvent.objects.filter(
            rule=rule,
            related_object_id=contract.id,
            created_at__gte=timezone.now() - timedelta(days=7),
        ).exists()

        if not recent:
            days_left = (contract.end_date - timezone.now().date()).days
            AlertEvent.objects.create(
                organization=org,
                rule=rule,
                severity=AlertEvent.Severity.WARNING,
                title=f"Contract Expiring: {contract.contract_number}",
                message=(
                    f"Contract '{contract.title}' with {contract.supplier.name} "
                    f"expires in {days_left} days ({contract.end_date})."
                ),
                related_object_type="contract",
                related_object_id=contract.id,
            )
            alerts_created += 1

    logger.info(
        "Contract expiry check: %d expiring, %d alerts created",
        expiring.count(),
        alerts_created,
    )
    return {"expiring_contracts": expiring.count(), "alerts_created": alerts_created}


@shared_task
def update_supplier_lead_times():
    """
    Update each supplier's average lead time based on actual PO delivery data.
    """
    from django.db.models import Avg
    from apps.procurement.models import PurchaseOrder
    from apps.suppliers.models import Supplier

    suppliers = Supplier.objects.filter(status=Supplier.Status.ACTIVE)
    updated = 0

    for supplier in suppliers:
        avg_lt = PurchaseOrder.objects.filter(
            supplier=supplier,
            actual_lead_time_days__isnull=False,
        ).aggregate(avg=Avg("actual_lead_time_days"))["avg"]

        if avg_lt is not None:
            new_lt = int(round(avg_lt))
            if supplier.lead_time_days != new_lt:
                supplier.lead_time_days = new_lt
                supplier.save(update_fields=["lead_time_days", "updated_at"])
                updated += 1

    logger.info("Supplier lead times updated: %d suppliers", updated)
    return {"suppliers_updated": updated}
