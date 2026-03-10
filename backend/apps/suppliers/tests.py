"""
Tests for suppliers app: models, services, and API endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User

from .models import Contract, Supplier, SupplierContact, SupplierRating
from .services import SupplierService


class SupplierModelTest(TestCase):
    """Test Supplier model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="sup@example.com",
            password="testpass12345",
            first_name="Sup",
            last_name="User",
            organization=self.org,
        )
        self.supplier = Supplier.objects.create(
            organization=self.org,
            name="Global Parts Inc",
            code="SUP-GPI-0001",
            category=Supplier.Category.COMPONENTS,
            created_by=self.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.supplier), "Global Parts Inc (SUP-GPI-0001)")

    def test_default_status(self):
        self.assertEqual(self.supplier.status, Supplier.Status.PENDING)

    def test_default_payment_terms(self):
        self.assertEqual(self.supplier.payment_terms, "Net 30")


class SupplierContactModelTest(TestCase):
    """Test SupplierContact model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Contact Test", code="SUP-CT-0001"
        )
        self.contact = SupplierContact.objects.create(
            supplier=self.supplier,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            is_primary=True,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.contact), "John Doe - Contact Test")

    def test_is_primary(self):
        self.assertTrue(self.contact.is_primary)


class ContractModelTest(TestCase):
    """Test Contract model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Contract Corp", code="SUP-CC-0001"
        )
        self.contract = Contract.objects.create(
            supplier=self.supplier,
            contract_number="CTR-001",
            title="Annual Supply Agreement",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=335),
            total_value=Decimal("100000.00"),
            status=Contract.Status.ACTIVE,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.contract), "CTR-001 - Annual Supply Agreement")

    def test_is_not_expired(self):
        self.assertFalse(self.contract.is_expired)

    def test_is_expired(self):
        self.contract.end_date = date.today() - timedelta(days=1)
        self.contract.save()
        self.assertTrue(self.contract.is_expired)


class SupplierRatingModelTest(TestCase):
    """Test SupplierRating model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.supplier = Supplier.objects.create(
            organization=self.org, name="Rated Co", code="SUP-RC-0001"
        )
        self.rating = SupplierRating.objects.create(
            supplier=self.supplier,
            dimension=SupplierRating.Dimension.QUALITY,
            score=Decimal("8.5"),
            period_start=date.today() - timedelta(days=90),
            period_end=date.today(),
        )

    def test_str_representation(self):
        self.assertIn("Rated Co", str(self.rating))
        self.assertIn("8.5", str(self.rating))


class SupplierServiceTest(TestCase):
    """Test SupplierService."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="svc@example.com",
            password="testpass12345",
            first_name="Svc",
            last_name="User",
            organization=self.org,
            role=User.Role.MANAGER,
        )

    def test_onboard_supplier(self):
        supplier = SupplierService.onboard_supplier(
            self.org,
            {"name": "New Vendor", "category": "components", "country": "US"},
            self.user,
        )
        self.assertEqual(supplier.status, Supplier.Status.PENDING)
        self.assertTrue(supplier.code.startswith("SUP-NEW"))

    def test_activate_supplier(self):
        supplier = SupplierService.onboard_supplier(
            self.org, {"name": "Activate Me"}, self.user
        )
        activated = SupplierService.activate_supplier(supplier)
        self.assertEqual(activated.status, Supplier.Status.ACTIVE)

    def test_activate_blocked_raises(self):
        supplier = Supplier.objects.create(
            organization=self.org,
            name="Blocked",
            code="SUP-BLK-0001",
            status=Supplier.Status.BLOCKED,
        )
        with self.assertRaises(ValueError):
            SupplierService.activate_supplier(supplier)

    def test_block_supplier(self):
        supplier = Supplier.objects.create(
            organization=self.org,
            name="To Block",
            code="SUP-TBK-0001",
            status=Supplier.Status.ACTIVE,
        )
        blocked = SupplierService.block_supplier(supplier, "Quality issues")
        self.assertEqual(blocked.status, Supplier.Status.BLOCKED)
        self.assertIn("BLOCKED", blocked.notes)


class SupplierAPITest(TestCase):
    """Test supplier API endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="api@example.com",
            password="testpass12345",
            first_name="API",
            last_name="User",
            organization=self.org,
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.supplier = Supplier.objects.create(
            organization=self.org,
            name="API Supplier",
            code="SUP-API-0001",
            status=Supplier.Status.ACTIVE,
            created_by=self.user,
        )

    def test_list_suppliers(self):
        response = self.client.get("/api/suppliers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_supplier(self):
        response = self.client.get(f"/api/suppliers/{self.supplier.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "API Supplier")

    def test_add_contact(self):
        response = self.client.post(
            f"/api/suppliers/{self.supplier.id}/contacts/",
            {
                "first_name": "New",
                "last_name": "Contact",
                "email": "new@example.com",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_rating(self):
        response = self.client.post(
            f"/api/suppliers/{self.supplier.id}/ratings/",
            {
                "dimension": "quality",
                "score": "8.0",
                "period_start": "2025-01-01",
                "period_end": "2025-03-31",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
