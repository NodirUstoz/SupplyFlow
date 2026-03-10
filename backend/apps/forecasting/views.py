"""
Forecasting views.
"""

from django.db.models import Avg, Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DemandForecast, ForecastAccuracy, ForecastConfiguration
from .serializers import (
    DemandForecastSerializer,
    ForecastAccuracySerializer,
    ForecastConfigurationSerializer,
    ForecastSummarySerializer,
)
from .services import AccuracyEvaluator, ForecastEngine


class ForecastConfigurationView(APIView):
    """Retrieve or update the organization's forecast configuration."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config, _ = ForecastConfiguration.objects.get_or_create(
            organization=request.user.organization,
        )
        serializer = ForecastConfigurationSerializer(config)
        return Response(serializer.data)

    def patch(self, request):
        config, _ = ForecastConfiguration.objects.get_or_create(
            organization=request.user.organization,
        )
        serializer = ForecastConfigurationSerializer(
            config, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DemandForecastViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to demand forecasts."""

    serializer_class = DemandForecastSerializer
    filterset_fields = ["inventory_item", "forecast_date", "method", "status"]
    ordering_fields = ["forecast_date", "predicted_quantity"]

    def get_queryset(self):
        user = self.request.user
        qs = DemandForecast.objects.select_related("inventory_item")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """
        Trigger forecast generation for the organization.

        Optional body: {"inventory_item_id": "<uuid>"}
        If provided, only that item is forecasted.
        """
        from apps.inventory.models import InventoryItem

        engine = ForecastEngine(request.user.organization)
        item = None
        item_id = request.data.get("inventory_item_id")
        if item_id:
            try:
                item = InventoryItem.objects.get(
                    id=item_id, organization=request.user.organization
                )
            except InventoryItem.DoesNotExist:
                return Response(
                    {"detail": "Inventory item not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        count = engine.generate_forecasts(item=item)
        return Response({"forecasts_created": count}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def publish(self, request):
        """Publish all draft forecasts, making them the active set."""
        updated = DemandForecast.objects.filter(
            organization=request.user.organization,
            status=DemandForecast.Status.DRAFT,
        ).update(status=DemandForecast.Status.PUBLISHED)
        return Response({"published": updated})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Aggregated forecast summary per item: average demand, accuracy, and
        recommended reorder quantity.
        """
        org = request.user.organization
        config, _ = ForecastConfiguration.objects.get_or_create(organization=org)

        forecasts = (
            DemandForecast.objects.filter(
                organization=org,
                status=DemandForecast.Status.PUBLISHED,
            )
            .values("inventory_item", "inventory_item__sku", "inventory_item__name")
            .annotate(
                avg_predicted=Avg("predicted_quantity"),
                forecast_count=Count("id"),
            )
        )

        results = []
        for row in forecasts:
            accuracy = ForecastAccuracy.objects.filter(
                inventory_item_id=row["inventory_item"],
                organization=org,
            ).aggregate(avg_pct=Avg("percentage_error"))

            avg_pred = float(row["avg_predicted"]) if row["avg_predicted"] else 0
            recommended = round(
                avg_pred * float(config.safety_stock_multiplier) * config.forecast_horizon_days,
                3,
            )

            results.append({
                "inventory_item_id": row["inventory_item"],
                "sku": row["inventory_item__sku"],
                "name": row["inventory_item__name"],
                "avg_predicted_quantity": row["avg_predicted"],
                "forecast_count": row["forecast_count"],
                "avg_accuracy_pct": accuracy["avg_pct"],
                "recommended_reorder_qty": recommended,
            })

        serializer = ForecastSummarySerializer(results, many=True)
        return Response(serializer.data)


class ForecastAccuracyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to forecast accuracy records."""

    serializer_class = ForecastAccuracySerializer
    filterset_fields = ["inventory_item", "method"]
    ordering_fields = ["forecast_date", "percentage_error"]

    def get_queryset(self):
        user = self.request.user
        qs = ForecastAccuracy.objects.select_related("inventory_item")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs
