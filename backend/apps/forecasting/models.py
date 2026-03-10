"""
Forecasting models: DemandForecast, ForecastConfiguration, ForecastAccuracy.

Uses historical demand data to generate forward-looking quantity predictions
for inventory items, enabling automated replenishment.
"""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ForecastConfiguration(models.Model):
    """
    Per-organization settings for the forecasting engine.
    """

    class Method(models.TextChoices):
        MOVING_AVERAGE = "moving_avg", "Moving Average"
        EXPONENTIAL_SMOOTHING = "exp_smooth", "Exponential Smoothing"
        LINEAR_REGRESSION = "linear_reg", "Linear Regression"
        SEASONAL_NAIVE = "seasonal_naive", "Seasonal Naive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="forecast_config",
    )
    default_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.MOVING_AVERAGE,
    )
    lookback_days = models.PositiveIntegerField(
        default=90,
        help_text="Number of historical days to consider.",
    )
    forecast_horizon_days = models.PositiveIntegerField(
        default=30,
        help_text="Number of days to forecast into the future.",
    )
    safety_stock_multiplier = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.5,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Multiplier applied to average demand for safety stock calculation.",
    )
    auto_reorder_enabled = models.BooleanField(
        default=False,
        help_text="If enabled, automatically generate purchase requisitions.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Forecast config for {self.organization.name}"


class DemandForecast(models.Model):
    """
    Predicted daily demand for an inventory item.

    Each record represents the forecasted quantity for a single item on a
    single future date.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="demand_forecasts",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="forecasts",
    )
    forecast_date = models.DateField(help_text="The date being forecasted")
    predicted_quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text="Predicted demand quantity for this date",
    )
    confidence_lower = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Lower bound of 95% confidence interval",
    )
    confidence_upper = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Upper bound of 95% confidence interval",
    )
    method = models.CharField(
        max_length=20,
        choices=ForecastConfiguration.Method.choices,
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT,
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["forecast_date"]
        unique_together = [("inventory_item", "forecast_date", "status")]

    def __str__(self):
        return (
            f"{self.inventory_item.sku} forecast {self.forecast_date}: "
            f"{self.predicted_quantity}"
        )


class ForecastAccuracy(models.Model):
    """
    Tracks how accurate past forecasts were once actual demand is known.
    Used to improve model selection and parameter tuning.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="forecast_accuracy",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.CASCADE,
        related_name="forecast_accuracy_records",
    )
    forecast_date = models.DateField()
    predicted_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    absolute_error = models.DecimalField(max_digits=12, decimal_places=3)
    percentage_error = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="MAPE for this data point",
    )
    method = models.CharField(max_length=20, choices=ForecastConfiguration.Method.choices)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-forecast_date"]
        unique_together = [("inventory_item", "forecast_date", "method")]

    def __str__(self):
        return (
            f"{self.inventory_item.sku} {self.forecast_date}: "
            f"predicted={self.predicted_quantity}, actual={self.actual_quantity}"
        )
