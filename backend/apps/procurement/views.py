"""
Procurement views.
"""

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ApprovalWorkflow, PurchaseOrder, PurchaseOrderLine, PurchaseRequisition
from .serializers import (
    ApprovalActionSerializer,
    ApprovalWorkflowSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderDetailSerializer,
    PurchaseOrderLineSerializer,
    PurchaseOrderListSerializer,
    PurchaseRequisitionSerializer,
)
from .services import PurchaseOrderService, RequisitionService


class PurchaseRequisitionViewSet(viewsets.ModelViewSet):
    """CRUD for purchase requisitions."""

    serializer_class = PurchaseRequisitionSerializer
    filterset_fields = ["status", "priority", "department"]
    search_fields = ["requisition_number", "title", "description"]
    ordering_fields = ["created_at", "required_date", "estimated_total"]

    def get_queryset(self):
        user = self.request.user
        qs = PurchaseRequisition.objects.select_related(
            "requested_by", "suggested_supplier", "organization"
        )
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit a requisition for approval."""
        requisition = self.get_object()
        approver_ids = request.data.get("approver_ids", [])
        if not approver_ids:
            return Response(
                {"detail": "At least one approver is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        approvers = list(User.objects.filter(id__in=approver_ids, is_active=True))
        if len(approvers) != len(approver_ids):
            return Response(
                {"detail": "One or more approver IDs are invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            workflows = RequisitionService.submit_for_approval(requisition, approvers)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ApprovalWorkflowSerializer(workflows, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def convert_to_po(self, request, pk=None):
        """Convert an approved requisition to a PO."""
        requisition = self.get_object()
        supplier_id = request.data.get("supplier_id") or (
            str(requisition.suggested_supplier_id) if requisition.suggested_supplier_id else None
        )
        if not supplier_id:
            return Response(
                {"detail": "supplier_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.suppliers.models import Supplier

        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            return Response(
                {"detail": "Supplier not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            po = RequisitionService.convert_to_po(requisition, supplier, request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PurchaseOrderDetailSerializer(po).data,
            status=status.HTTP_201_CREATED,
        )


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """CRUD for purchase orders."""

    filterset_fields = ["status", "supplier", "currency"]
    search_fields = ["po_number", "supplier__name"]
    ordering_fields = ["created_at", "order_date", "total_amount", "expected_delivery_date"]

    def get_queryset(self):
        user = self.request.user
        qs = PurchaseOrder.objects.select_related(
            "supplier", "created_by", "approved_by", "organization"
        ).prefetch_related("lines")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return PurchaseOrderListSerializer
        if self.action == "create":
            return PurchaseOrderCreateSerializer
        return PurchaseOrderDetailSerializer

    @action(detail=True, methods=["post"])
    def submit_for_approval(self, request, pk=None):
        """Submit PO for multi-level approval."""
        po = self.get_object()
        approver_ids = request.data.get("approver_ids", [])
        if not approver_ids:
            return Response(
                {"detail": "At least one approver is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        approvers = list(User.objects.filter(id__in=approver_ids, is_active=True))
        try:
            workflows = PurchaseOrderService.submit_for_approval(po, approvers)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ApprovalWorkflowSerializer(workflows, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        """Record receipt of goods against a PO."""
        po = self.get_object()
        received_lines = request.data.get("lines", {})
        if not received_lines:
            return Response(
                {"detail": "lines dict required: {line_id: quantity}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            PurchaseOrderService.receive_delivery(po, received_lines)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PurchaseOrderDetailSerializer(po).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a purchase order."""
        po = self.get_object()
        if po.status in (PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CLOSED):
            return Response(
                {"detail": "Cannot cancel a received or closed PO."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        po.status = PurchaseOrder.Status.CANCELLED
        po.save(update_fields=["status", "updated_at"])
        return Response(PurchaseOrderDetailSerializer(po).data)


class PurchaseOrderLineViewSet(viewsets.ModelViewSet):
    """CRUD for PO line items."""

    serializer_class = PurchaseOrderLineSerializer
    filterset_fields = ["purchase_order"]

    def get_queryset(self):
        user = self.request.user
        qs = PurchaseOrderLine.objects.select_related("purchase_order")
        if not user.is_superuser:
            qs = qs.filter(purchase_order__organization=user.organization)
        return qs

    def perform_create(self, serializer):
        line = serializer.save()
        line.purchase_order.recalculate_totals()

    def perform_update(self, serializer):
        line = serializer.save()
        line.purchase_order.recalculate_totals()

    def perform_destroy(self, instance):
        po = instance.purchase_order
        instance.delete()
        po.recalculate_totals()


class ApprovalWorkflowViewSet(viewsets.ModelViewSet):
    """View and act on approval workflows."""

    serializer_class = ApprovalWorkflowSerializer
    filterset_fields = ["target_type", "decision"]

    def get_queryset(self):
        user = self.request.user
        qs = ApprovalWorkflow.objects.select_related("approver", "organization")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    @action(detail=False, methods=["get"])
    def my_pending(self, request):
        """List pending approvals assigned to the current user."""
        pending = self.get_queryset().filter(
            approver=request.user,
            decision=ApprovalWorkflow.Decision.PENDING,
        )
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        """Submit an approval decision."""
        workflow = self.get_object()
        if workflow.approver != request.user and not request.user.is_superuser:
            return Response(
                {"detail": "You are not the assigned approver."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = PurchaseOrderService.process_approval(
                workflow,
                serializer.validated_data["decision"],
                serializer.validated_data.get("comments", ""),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ApprovalWorkflowSerializer(updated).data)
