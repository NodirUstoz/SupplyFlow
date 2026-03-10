"""
Procurement business-logic services.
"""

import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ApprovalWorkflow, PurchaseOrder, PurchaseRequisition

logger = logging.getLogger(__name__)


class RequisitionService:
    """Service layer for purchase requisition operations."""

    @staticmethod
    def generate_requisition_number(organization) -> str:
        """Generate a unique requisition number: REQ-YYYYMMDD-XXXX."""
        today = date.today().strftime("%Y%m%d")
        last = (
            PurchaseRequisition.objects.filter(
                organization=organization,
                requisition_number__startswith=f"REQ-{today}",
            )
            .order_by("-requisition_number")
            .first()
        )
        if last:
            seq = int(last.requisition_number.split("-")[-1]) + 1
        else:
            seq = 1
        return f"REQ-{today}-{seq:04d}"

    @staticmethod
    @transaction.atomic
    def submit_for_approval(requisition: PurchaseRequisition, approvers: list) -> list:
        """
        Submit a requisition for approval and create workflow steps.
        Returns the list of created ApprovalWorkflow instances.
        """
        if requisition.status != PurchaseRequisition.Status.DRAFT:
            raise ValueError("Only draft requisitions can be submitted for approval.")

        requisition.status = PurchaseRequisition.Status.SUBMITTED
        requisition.save(update_fields=["status", "updated_at"])

        workflows = []
        for idx, approver in enumerate(approvers, start=1):
            wf = ApprovalWorkflow.objects.create(
                organization=requisition.organization,
                target_type=ApprovalWorkflow.TargetType.REQUISITION,
                target_id=requisition.id,
                step_order=idx,
                approver=approver,
            )
            workflows.append(wf)
        return workflows

    @staticmethod
    @transaction.atomic
    def convert_to_po(requisition: PurchaseRequisition, supplier, created_by) -> PurchaseOrder:
        """Convert an approved requisition into a purchase order."""
        if requisition.status != PurchaseRequisition.Status.APPROVED:
            raise ValueError("Only approved requisitions can be converted.")

        po_number = PurchaseOrderService.generate_po_number(requisition.organization)

        po = PurchaseOrder.objects.create(
            organization=requisition.organization,
            po_number=po_number,
            supplier=supplier,
            currency=requisition.currency,
            payment_terms=supplier.payment_terms,
            created_by=created_by,
        )
        requisition.status = PurchaseRequisition.Status.CONVERTED
        requisition.purchase_order = po
        requisition.save(update_fields=["status", "purchase_order", "updated_at"])

        logger.info(
            "Requisition %s converted to PO %s",
            requisition.requisition_number,
            po.po_number,
        )
        return po


class PurchaseOrderService:
    """Service layer for purchase order operations."""

    @staticmethod
    def generate_po_number(organization) -> str:
        """Generate a unique PO number: PO-YYYYMMDD-XXXX."""
        today = date.today().strftime("%Y%m%d")
        last = (
            PurchaseOrder.objects.filter(
                organization=organization,
                po_number__startswith=f"PO-{today}",
            )
            .order_by("-po_number")
            .first()
        )
        if last:
            seq = int(last.po_number.split("-")[-1]) + 1
        else:
            seq = 1
        return f"PO-{today}-{seq:04d}"

    @staticmethod
    @transaction.atomic
    def submit_for_approval(po: PurchaseOrder, approvers: list) -> list:
        """Submit a PO for multi-level approval."""
        if po.status != PurchaseOrder.Status.DRAFT:
            raise ValueError("Only draft purchase orders can be submitted.")

        if not po.lines.exists():
            raise ValueError("Cannot submit a PO with no line items.")

        po.status = PurchaseOrder.Status.PENDING_APPROVAL
        po.save(update_fields=["status", "updated_at"])

        workflows = []
        for idx, approver in enumerate(approvers, start=1):
            wf = ApprovalWorkflow.objects.create(
                organization=po.organization,
                target_type=ApprovalWorkflow.TargetType.PURCHASE_ORDER,
                target_id=po.id,
                step_order=idx,
                approver=approver,
            )
            workflows.append(wf)
        return workflows

    @staticmethod
    @transaction.atomic
    def process_approval(workflow: ApprovalWorkflow, decision: str, comments: str = "") -> ApprovalWorkflow:
        """Process a single approval step."""
        if workflow.decision != ApprovalWorkflow.Decision.PENDING:
            raise ValueError("This approval step has already been decided.")

        workflow.decision = decision
        workflow.comments = comments
        workflow.decided_at = timezone.now()
        workflow.save()

        if decision == ApprovalWorkflow.Decision.REJECTED:
            # Reject the whole PO
            if workflow.target_type == ApprovalWorkflow.TargetType.PURCHASE_ORDER:
                PurchaseOrder.objects.filter(id=workflow.target_id).update(
                    status=PurchaseOrder.Status.DRAFT
                )
            elif workflow.target_type == ApprovalWorkflow.TargetType.REQUISITION:
                PurchaseRequisition.objects.filter(id=workflow.target_id).update(
                    status=PurchaseRequisition.Status.REJECTED
                )
            logger.info("Workflow %s rejected by %s", workflow.id, workflow.approver)
            return workflow

        # Check if all steps are approved
        all_approved = not ApprovalWorkflow.objects.filter(
            target_type=workflow.target_type,
            target_id=workflow.target_id,
            decision=ApprovalWorkflow.Decision.PENDING,
        ).exists()

        if all_approved:
            if workflow.target_type == ApprovalWorkflow.TargetType.PURCHASE_ORDER:
                po = PurchaseOrder.objects.get(id=workflow.target_id)
                po.status = PurchaseOrder.Status.APPROVED
                po.approved_by = workflow.approver
                po.approved_at = timezone.now()
                po.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
                logger.info("PO %s fully approved", po.po_number)
            elif workflow.target_type == ApprovalWorkflow.TargetType.REQUISITION:
                PurchaseRequisition.objects.filter(id=workflow.target_id).update(
                    status=PurchaseRequisition.Status.APPROVED
                )

        return workflow

    @staticmethod
    @transaction.atomic
    def receive_delivery(po: PurchaseOrder, received_lines: dict):
        """
        Record partial or full delivery against a PO.

        received_lines: {line_id: quantity_received}
        """
        for line_id, qty in received_lines.items():
            line = po.lines.get(id=line_id)
            line.quantity_received = min(
                line.quantity_received + Decimal(str(qty)),
                line.quantity,
            )
            line.save(update_fields=["quantity_received"])

        # Determine if all lines are fully received
        all_received = all(
            l.quantity_received >= l.quantity for l in po.lines.all()
        )

        if all_received:
            po.status = PurchaseOrder.Status.RECEIVED
            po.actual_delivery_date = timezone.now().date()
            delta = (po.actual_delivery_date - po.order_date).days
            po.actual_lead_time_days = max(delta, 0)
        else:
            po.status = PurchaseOrder.Status.PARTIALLY_RECEIVED

        po.save(update_fields=["status", "actual_delivery_date", "actual_lead_time_days", "updated_at"])
        logger.info("PO %s delivery recorded, status: %s", po.po_number, po.status)
