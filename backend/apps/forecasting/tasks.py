"""
Celery tasks for demand forecasting.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_forecasts():
    """
    Generate demand forecasts for all active organizations.
    Scheduled to run daily at 02:00 UTC via Celery Beat.
    """
    from apps.accounts.models import Organization
    from .services import ForecastEngine

    organizations = Organization.objects.filter(is_active=True)
    total = 0

    for org in organizations:
        try:
            engine = ForecastEngine(org)
            count = engine.generate_forecasts()
            total += count
            logger.info(
                "Generated %d forecasts for org %s", count, org.name
            )
        except Exception:
            logger.exception(
                "Failed to generate forecasts for org %s", org.name
            )

    return {"total_forecasts_generated": total}


@shared_task
def evaluate_forecast_accuracy():
    """
    Evaluate yesterday's forecasts against actual demand.
    Scheduled to run daily at 04:00 UTC.
    """
    from apps.accounts.models import Organization
    from .services import AccuracyEvaluator

    organizations = Organization.objects.filter(is_active=True)
    total = 0

    for org in organizations:
        try:
            count = AccuracyEvaluator.evaluate(org)
            total += count
        except Exception:
            logger.exception(
                "Failed to evaluate forecast accuracy for org %s", org.name
            )

    logger.info("Evaluated %d forecast accuracy records", total)
    return {"total_evaluated": total}


@shared_task
def auto_generate_reorder_requisitions():
    """
    For organizations with auto-reorder enabled, check forecast-based
    recommendations against current stock and create purchase requisitions
    where needed.
    """
    from decimal import Decimal
    from apps.inventory.models import InventoryItem
    from apps.procurement.services import RequisitionService
    from .models import DemandForecast, ForecastConfiguration

    configs = ForecastConfiguration.objects.filter(auto_reorder_enabled=True)
    requisitions_created = 0

    for config in configs:
        org = config.organization
        items = InventoryItem.objects.filter(organization=org, is_active=True)

        for item in items:
            if not item.is_below_reorder_point:
                continue

            # Check if there are published forecasts suggesting sustained demand
            avg_forecast = DemandForecast.objects.filter(
                inventory_item=item,
                status=DemandForecast.Status.PUBLISHED,
            ).aggregate(
                avg_qty=models_avg("predicted_quantity")
            )

            forecasted_demand = avg_forecast.get("avg_qty") or Decimal("0")
            if forecasted_demand > 0:
                reorder_qty = max(
                    item.reorder_quantity,
                    forecasted_demand * config.forecast_horizon_days * config.safety_stock_multiplier,
                )

                logger.info(
                    "Auto-reorder: %s needs %.0f units (forecast-based)",
                    item.sku,
                    reorder_qty,
                )
                requisitions_created += 1

    logger.info("Auto-reorder check complete: %d items flagged", requisitions_created)
    return {"requisitions_flagged": requisitions_created}


def models_avg(field_name):
    """Helper to avoid circular import of Django aggregation."""
    from django.db.models import Avg
    return Avg(field_name)
