"""
Analytics views: dashboard summary, metric snapshots, KPI targets, alerts.
"""

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import InventoryItem, StockLevel
from apps.procurement.models import ApprovalWorkflow, PurchaseOrder
from apps.shipments.models import Shipment
from apps.suppliers.models import Supplier

from .models import AlertEvent, AlertRule, DashboardMetricSnapshot, KPITarget
from .serializers import (
    AlertEventSerializer,
    AlertRuleSerializer,
    DashboardMetricSnapshotSerializer,
    DashboardSummarySerializer,
    KPITargetSerializer,
)


class DashboardSummaryView(APIView):
    """
    Return a live summary of all key supply-chain metrics for the
    authenticated user's organization.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        org = request.user.organization

        # Purchase orders
        po_qs = PurchaseOrder.objects.filter(organization=org)
        open_statuses = [
            PurchaseOrder.Status.DRAFT,
            PurchaseOrder.Status.PENDING_APPROVAL,
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.SENT,
            PurchaseOrder.Status.ACKNOWLEDGED,
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
        ]
        open_po = po_qs.filter(status__in=open_statuses)
        total_po_value = open_po.aggregate(total=Sum("total_amount"))["total"] or 0

        # Inventory
        stock_qs = StockLevel.objects.filter(item__organization=org)
        inventory_value = stock_qs.aggregate(
            total=Sum(F("quantity") * F("item__unit_cost"))
        )["total"] or 0

        items = InventoryItem.objects.filter(organization=org, is_active=True)
        low_stock_count = sum(1 for item in items if item.is_below_reorder_point)

        # Shipments
        active_statuses = [
            Shipment.Status.PICKED_UP,
            Shipment.Status.IN_TRANSIT,
            Shipment.Status.CUSTOMS,
            Shipment.Status.OUT_FOR_DELIVERY,
        ]
        active_shipments = Shipment.objects.filter(
            organization=org, status__in=active_statuses
        ).count()

        # On-time delivery
        delivered = Shipment.objects.filter(
            organization=org,
            status=Shipment.Status.DELIVERED,
            actual_arrival__isnull=False,
            estimated_arrival__isnull=False,
        )
        if delivered.exists():
            on_time = delivered.filter(actual_arrival__lte=F("estimated_arrival")).count()
            on_time_rate = round(on_time / delivered.count() * 100, 2)
        else:
            on_time_rate = None

        # Suppliers
        avg_score = Supplier.objects.filter(
            organization=org, status="active"
        ).aggregate(avg=Avg("overall_score"))["avg"]

        # Pending approvals
        pending_approvals = ApprovalWorkflow.objects.filter(
            organization=org,
            decision=ApprovalWorkflow.Decision.PENDING,
        ).count()

        # Unread alerts
        unread_alerts = AlertEvent.objects.filter(
            organization=org, is_read=False
        ).count()

        data = {
            "total_po_value": total_po_value,
            "open_po_count": open_po.count(),
            "inventory_value": inventory_value,
            "low_stock_count": low_stock_count,
            "active_shipments": active_shipments,
            "on_time_delivery_rate": on_time_rate,
            "avg_supplier_score": round(avg_score, 2) if avg_score else None,
            "pending_approvals": pending_approvals,
            "unread_alerts": unread_alerts,
        }
        serializer = DashboardSummarySerializer(data)
        return Response(serializer.data)


class MetricSnapshotViewSet(viewsets.ModelViewSet):
    """CRUD for metric snapshots (typically created by scheduled tasks)."""

    serializer_class = DashboardMetricSnapshotSerializer
    filterset_fields = ["metric_name", "snapshot_date"]
    ordering_fields = ["snapshot_date", "value"]

    def get_queryset(self):
        user = self.request.user
        qs = DashboardMetricSnapshot.objects.all()
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=False, methods=["get"])
    def trends(self, request):
        """
        Return the last 30 days of snapshots for a given metric.

        Query params:
            - metric_name (required)
            - days (optional, default 30)
        """
        metric_name = request.query_params.get("metric_name")
        if not metric_name:
            return Response(
                {"detail": "metric_name query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        days = int(request.query_params.get("days", 30))
        cutoff = timezone.now().date() - timezone.timedelta(days=days)

        snapshots = self.get_queryset().filter(
            metric_name=metric_name,
            snapshot_date__gte=cutoff,
        ).order_by("snapshot_date")

        serializer = self.get_serializer(snapshots, many=True)
        return Response(serializer.data)


class KPITargetViewSet(viewsets.ModelViewSet):
    """CRUD for KPI targets."""

    serializer_class = KPITargetSerializer
    filterset_fields = ["metric_name", "is_active"]

    def get_queryset(self):
        user = self.request.user
        qs = KPITarget.objects.select_related("created_by")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs


class AlertRuleViewSet(viewsets.ModelViewSet):
    """CRUD for alert rules."""

    serializer_class = AlertRuleSerializer
    filterset_fields = ["rule_type", "is_active", "channel"]
    search_fields = ["name"]

    def get_queryset(self):
        user = self.request.user
        qs = AlertRule.objects.all()
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs


class AlertEventViewSet(viewsets.ModelViewSet):
    """View and manage alert events."""

    serializer_class = AlertEventSerializer
    filterset_fields = ["severity", "is_read", "rule"]
    ordering_fields = ["created_at", "severity"]

    def get_queryset(self):
        user = self.request.user
        qs = AlertEvent.objects.select_related("rule", "read_by")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark an alert event as read."""
        event = self.get_object()
        event.is_read = True
        event.read_by = request.user
        event.read_at = timezone.now()
        event.save(update_fields=["is_read", "read_by", "read_at"])
        return Response(AlertEventSerializer(event).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all unread alert events as read for the user's organization."""
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_by=request.user,
            read_at=timezone.now(),
        )
        return Response({"marked_read": updated})
