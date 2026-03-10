"""
Tests for procurement app: models, services, and API endpoints.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.suppliers.models import Supplier

from .models import ApprovalWorkflow, PurchaseOrder, PurchaseOrderLine, PurchaseRequisition
from .services import PurchaseOrderService, RequisitionService


class PurchaseRequisitionModelTest(TestCase):
    """Test PurchaseRequisition model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="testpass12345",
            first_name="Jane",
            last_name="Buyer",
            organization=self.org,
            role=User.Role.BUYER,
        )
        self.req = PurchaseRequisition.objects.create(
            organization=self.org,
            requisition_number="REQ-TEST-0001",
            title="Office Supplies",
            requested_by=self.user,
            estimated_total=Decimal("500.00"),
            priority=PurchaseRequisition.Priority.MEDIUM,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.req), "REQ-TEST-0001 - Office Supplies")

    def test_default_status(self):
        self.assertEqual(self.req.status, PurchaseRequisition.Status.DRAFT)


class PurchaseOrderModelTest(TestCase):
    """Test PurchaseOrder model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Acme Corp", code="SUP-ACM-0001"
        )
        self.user = User.objects.create_user(
            email="po@example.com",
            password="testpass12345",
            first_name="PO",
            last_name="Creator",
            organization=self.org,
        )
        self.po = PurchaseOrder.objects.create(
            organization=self.org,
            po_number="PO-TEST-0001",
            supplier=self.supplier,
            created_by=self.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.po), "PO-TEST-0001 - Acme Corp")

    def test_default_status(self):
        self.assertEqual(self.po.status, PurchaseOrder.Status.DRAFT)

    def test_recalculate_totals(self):
        PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            line_number=1,
            item_code="ITEM-A",
            description="Widget A",
            quantity=Decimal("10"),
            unit_price=Decimal("25.00"),
        )
        PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            line_number=2,
            item_code="ITEM-B",
            description="Widget B",
            quantity=Decimal("5"),
            unit_price=Decimal("50.00"),
        )
        self.po.recalculate_totals()
        self.po.refresh_from_db()
        self.assertEqual(self.po.subtotal, Decimal("500"))
        self.assertEqual(self.po.total_amount, Decimal("500"))


class RequisitionServiceTest(TestCase):
    """Test RequisitionService."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="req-svc@example.com",
            password="testpass12345",
            first_name="Req",
            last_name="Service",
            organization=self.org,
            role=User.Role.BUYER,
        )
        self.approver = User.objects.create_user(
            email="approver@example.com",
            password="testpass12345",
            first_name="App",
            last_name="Rover",
            organization=self.org,
            role=User.Role.MANAGER,
        )
        self.req = PurchaseRequisition.objects.create(
            organization=self.org,
            requisition_number="REQ-SVC-0001",
            title="Test Requisition",
            requested_by=self.user,
        )

    def test_generate_requisition_number(self):
        number = RequisitionService.generate_requisition_number(self.org)
        self.assertTrue(number.startswith("REQ-"))
        self.assertEqual(len(number.split("-")), 3)

    def test_submit_for_approval(self):
        workflows = RequisitionService.submit_for_approval(
            self.req, [self.approver]
        )
        self.assertEqual(len(workflows), 1)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, PurchaseRequisition.Status.SUBMITTED)

    def test_submit_non_draft_raises(self):
        self.req.status = PurchaseRequisition.Status.SUBMITTED
        self.req.save()
        with self.assertRaises(ValueError):
            RequisitionService.submit_for_approval(self.req, [self.approver])


class PurchaseOrderServiceTest(TestCase):
    """Test PurchaseOrderService."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Vendor X", code="SUP-VND-0001"
        )
        self.user = User.objects.create_user(
            email="po-svc@example.com",
            password="testpass12345",
            first_name="PO",
            last_name="Service",
            organization=self.org,
            role=User.Role.MANAGER,
        )
        self.po = PurchaseOrder.objects.create(
            organization=self.org,
            po_number="PO-SVC-0001",
            supplier=self.supplier,
            created_by=self.user,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            line_number=1,
            item_code="TEST-ITEM",
            description="Test",
            quantity=Decimal("100"),
            unit_price=Decimal("10.00"),
        )

    def test_generate_po_number(self):
        number = PurchaseOrderService.generate_po_number(self.org)
        self.assertTrue(number.startswith("PO-"))

    def test_submit_for_approval(self):
        workflows = PurchaseOrderService.submit_for_approval(
            self.po, [self.user]
        )
        self.assertEqual(len(workflows), 1)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PENDING_APPROVAL)

    def test_submit_empty_po_raises(self):
        empty_po = PurchaseOrder.objects.create(
            organization=self.org,
            po_number="PO-EMPTY-0001",
            supplier=self.supplier,
            created_by=self.user,
        )
        with self.assertRaises(ValueError):
            PurchaseOrderService.submit_for_approval(empty_po, [self.user])

    def test_receive_full_delivery(self):
        self.po.status = PurchaseOrder.Status.APPROVED
        self.po.save()
        line = self.po.lines.first()
        PurchaseOrderService.receive_delivery(
            self.po, {str(line.id): "100"}
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.RECEIVED)

    def test_receive_partial_delivery(self):
        self.po.status = PurchaseOrder.Status.APPROVED
        self.po.save()
        line = self.po.lines.first()
        PurchaseOrderService.receive_delivery(
            self.po, {str(line.id): "50"}
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PARTIALLY_RECEIVED)


class ApprovalWorkflowTest(TestCase):
    """Test the approval workflow process."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Supplier Z", code="SUP-Z-0001"
        )
        self.creator = User.objects.create_user(
            email="creator@example.com",
            password="testpass12345",
            first_name="Creator",
            last_name="User",
            organization=self.org,
        )
        self.approver1 = User.objects.create_user(
            email="approver1@example.com",
            password="testpass12345",
            first_name="Approver",
            last_name="One",
            organization=self.org,
            role=User.Role.MANAGER,
        )
        self.approver2 = User.objects.create_user(
            email="approver2@example.com",
            password="testpass12345",
            first_name="Approver",
            last_name="Two",
            organization=self.org,
            role=User.Role.ADMIN,
        )
        self.po = PurchaseOrder.objects.create(
            organization=self.org,
            po_number="PO-WF-0001",
            supplier=self.supplier,
            created_by=self.creator,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=self.po,
            line_number=1,
            item_code="WF-ITEM",
            description="Workflow Test",
            quantity=Decimal("10"),
            unit_price=Decimal("100.00"),
        )

    def test_multi_step_approval(self):
        workflows = PurchaseOrderService.submit_for_approval(
            self.po, [self.approver1, self.approver2]
        )
        self.assertEqual(len(workflows), 2)

        # First approval
        PurchaseOrderService.process_approval(
            workflows[0], ApprovalWorkflow.Decision.APPROVED
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.PENDING_APPROVAL)

        # Second approval -- should fully approve
        PurchaseOrderService.process_approval(
            workflows[1], ApprovalWorkflow.Decision.APPROVED
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.APPROVED)

    def test_rejection_stops_process(self):
        workflows = PurchaseOrderService.submit_for_approval(
            self.po, [self.approver1, self.approver2]
        )
        PurchaseOrderService.process_approval(
            workflows[0], ApprovalWorkflow.Decision.REJECTED, "Not within budget"
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.Status.DRAFT)
