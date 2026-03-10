"""
Forecasting engine: demand prediction using simple statistical models.

All methods operate on a list of historical daily demand quantities and
produce a list of predictions for the configured horizon.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import InventoryItem
from apps.procurement.models import PurchaseOrderLine

from .models import DemandForecast, ForecastAccuracy, ForecastConfiguration

logger = logging.getLogger(__name__)


class ForecastEngine:
    """Core forecasting engine supporting multiple prediction methods."""

    def __init__(self, organization):
        self.organization = organization
        self.config = self._get_or_create_config()

    def _get_or_create_config(self) -> ForecastConfiguration:
        config, _ = ForecastConfiguration.objects.get_or_create(
            organization=self.organization,
            defaults={
                "default_method": ForecastConfiguration.Method.MOVING_AVERAGE,
                "lookback_days": 90,
                "forecast_horizon_days": 30,
            },
        )
        return config

    def generate_forecasts(self, item: Optional[InventoryItem] = None):
        """
        Generate forecasts for all active items (or a single item).
        Marks previous drafts as superseded.
        """
        if item:
            items = [item]
        else:
            items = InventoryItem.objects.filter(
                organization=self.organization, is_active=True
            )

        today = date.today()
        created_count = 0

        for inv_item in items:
            history = self._get_demand_history(inv_item)
            if len(history) < 7:
                logger.debug("Insufficient history for %s, skipping", inv_item.sku)
                continue

            # Supersede old draft forecasts for this item
            DemandForecast.objects.filter(
                inventory_item=inv_item,
                status=DemandForecast.Status.DRAFT,
            ).update(status=DemandForecast.Status.SUPERSEDED)

            method = self.config.default_method
            predictions = self._predict(history, method)

            for day_offset, qty in enumerate(predictions, start=1):
                forecast_date = today + timedelta(days=day_offset)
                lower, upper = self._confidence_bounds(qty, history)

                DemandForecast.objects.create(
                    organization=self.organization,
                    inventory_item=inv_item,
                    forecast_date=forecast_date,
                    predicted_quantity=max(Decimal("0"), qty),
                    confidence_lower=max(Decimal("0"), lower),
                    confidence_upper=upper,
                    method=method,
                    status=DemandForecast.Status.DRAFT,
                )
                created_count += 1

        logger.info(
            "Generated %d forecast records for org %s",
            created_count,
            self.organization.name,
        )
        return created_count

    def _get_demand_history(self, item: InventoryItem) -> List[Decimal]:
        """
        Extract daily demand quantities from PO line history.
        Returns a list of daily totals for the lookback period.
        """
        cutoff = date.today() - timedelta(days=self.config.lookback_days)

        # Aggregate quantity ordered per day from PO lines
        daily = (
            PurchaseOrderLine.objects.filter(
                inventory_item=item,
                purchase_order__order_date__gte=cutoff,
            )
            .values("purchase_order__order_date")
            .annotate(total_qty=Sum("quantity"))
            .order_by("purchase_order__order_date")
        )

        # Fill gaps with zeros for days with no orders
        history_map = {
            row["purchase_order__order_date"]: row["total_qty"]
            for row in daily
        }

        result = []
        current = cutoff
        today = date.today()
        while current <= today:
            result.append(history_map.get(current, Decimal("0")))
            current += timedelta(days=1)

        return result

    def _predict(self, history: List[Decimal], method: str) -> List[Decimal]:
        """Dispatch to the appropriate forecasting method."""
        horizon = self.config.forecast_horizon_days
        if method == ForecastConfiguration.Method.MOVING_AVERAGE:
            return self._moving_average(history, horizon)
        elif method == ForecastConfiguration.Method.EXPONENTIAL_SMOOTHING:
            return self._exponential_smoothing(history, horizon)
        elif method == ForecastConfiguration.Method.LINEAR_REGRESSION:
            return self._linear_regression(history, horizon)
        elif method == ForecastConfiguration.Method.SEASONAL_NAIVE:
            return self._seasonal_naive(history, horizon)
        return self._moving_average(history, horizon)

    @staticmethod
    def _moving_average(history: List[Decimal], horizon: int, window: int = 7) -> List[Decimal]:
        """Simple moving average using the last `window` data points."""
        if not history:
            return [Decimal("0")] * horizon
        recent = history[-window:]
        avg = sum(recent) / len(recent)
        return [Decimal(str(round(float(avg), 3)))] * horizon

    @staticmethod
    def _exponential_smoothing(
        history: List[Decimal], horizon: int, alpha: float = 0.3
    ) -> List[Decimal]:
        """Single exponential smoothing (SES)."""
        if not history:
            return [Decimal("0")] * horizon
        level = float(history[0])
        for val in history[1:]:
            level = alpha * float(val) + (1 - alpha) * level
        return [Decimal(str(round(level, 3)))] * horizon

    @staticmethod
    def _linear_regression(history: List[Decimal], horizon: int) -> List[Decimal]:
        """Simple linear regression on the time series index."""
        n = len(history)
        if n < 2:
            return [Decimal("0")] * horizon

        x_vals = list(range(n))
        y_vals = [float(v) for v in history]

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            return [Decimal(str(round(y_mean, 3)))] * horizon

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        predictions = []
        for i in range(horizon):
            future_x = n + i
            pred = slope * future_x + intercept
            predictions.append(Decimal(str(round(max(pred, 0), 3))))
        return predictions

    @staticmethod
    def _seasonal_naive(history: List[Decimal], horizon: int, season_length: int = 7) -> List[Decimal]:
        """Repeat the last full season (default weekly cycle)."""
        if len(history) < season_length:
            avg = sum(history) / len(history) if history else Decimal("0")
            return [Decimal(str(round(float(avg), 3)))] * horizon

        last_season = history[-season_length:]
        predictions = []
        for i in range(horizon):
            predictions.append(last_season[i % season_length])
        return predictions

    @staticmethod
    def _confidence_bounds(
        prediction: Decimal, history: List[Decimal], z: float = 1.96
    ) -> Tuple[Decimal, Decimal]:
        """Compute 95% confidence interval based on historical standard deviation."""
        if len(history) < 2:
            return prediction, prediction

        values = [float(v) for v in history]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std_dev = variance ** 0.5

        pred_f = float(prediction)
        lower = Decimal(str(round(pred_f - z * std_dev, 3)))
        upper = Decimal(str(round(pred_f + z * std_dev, 3)))
        return lower, upper


class AccuracyEvaluator:
    """Compare past forecasts against actual outcomes to measure accuracy."""

    @staticmethod
    def evaluate(organization, evaluation_date: date = None):
        """
        For each published forecast whose date has passed, compare
        predicted vs. actual and store an accuracy record.
        """
        if evaluation_date is None:
            evaluation_date = date.today() - timedelta(days=1)

        forecasts = DemandForecast.objects.filter(
            organization=organization,
            forecast_date=evaluation_date,
            status=DemandForecast.Status.PUBLISHED,
        ).select_related("inventory_item")

        created = 0
        for fc in forecasts:
            actual = (
                PurchaseOrderLine.objects.filter(
                    inventory_item=fc.inventory_item,
                    purchase_order__order_date=evaluation_date,
                ).aggregate(total=Sum("quantity"))["total"]
                or Decimal("0")
            )

            abs_error = abs(fc.predicted_quantity - actual)
            pct_error = None
            if actual > 0:
                pct_error = Decimal(str(
                    round(float(abs_error / actual) * 100, 4)
                ))

            ForecastAccuracy.objects.update_or_create(
                inventory_item=fc.inventory_item,
                forecast_date=evaluation_date,
                method=fc.method,
                defaults={
                    "organization": organization,
                    "predicted_quantity": fc.predicted_quantity,
                    "actual_quantity": actual,
                    "absolute_error": abs_error,
                    "percentage_error": pct_error,
                },
            )
            created += 1

        logger.info(
            "Evaluated %d forecasts for %s on %s",
            created,
            organization.name,
            evaluation_date,
        )
        return created
