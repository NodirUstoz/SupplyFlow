"""
Tests for inventory app: models, services, and API endpoints.
"""

import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User

from .models import InventoryItem, StockLevel, Warehouse
from .services import StockService


class WarehouseModelTest(TestCase):
    """Test the Warehouse model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.warehouse = Warehouse.objects.create(
            organization=self.org,
            name="Main Warehouse",
            code="WH-001",
            city="Dallas",
            country="US",
            capacity=10000,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.warehouse), "Main Warehouse (WH-001)")

    def test_warehouse_defaults(self):
        self.assertTrue(self.warehouse.is_active)
        self.assertEqual(self.warehouse.country, "US")


class InventoryItemModelTest(TestCase):
    """Test the InventoryItem model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.warehouse = Warehouse.objects.create(
            organization=self.org, name="WH", code="WH-T1"
        )
        self.item = InventoryItem.objects.create(
            organization=self.org,
            sku="ITEM-001",
            name="Widget A",
            category=InventoryItem.Category.COMPONENT,
            unit_cost=Decimal("12.50"),
            reorder_point=Decimal("100"),
            reorder_quantity=Decimal("500"),
        )

    def test_str_representation(self):
        self.assertEqual(str(self.item), "ITEM-001 - Widget A")

    def test_total_stock_no_levels(self):
        self.assertEqual(self.item.total_stock, 0)

    def test_total_stock_with_levels(self):
        StockLevel.objects.create(
            item=self.item, warehouse=self.warehouse, quantity=Decimal("75")
        )
        self.assertEqual(self.item.total_stock, Decimal("75"))

    def test_is_below_reorder_point(self):
        StockLevel.objects.create(
            item=self.item, warehouse=self.warehouse, quantity=Decimal("50")
        )
        self.assertTrue(self.item.is_below_reorder_point)

    def test_not_below_reorder_point(self):
        StockLevel.objects.create(
            item=self.item, warehouse=self.warehouse, quantity=Decimal("500")
        )
        self.assertFalse(self.item.is_below_reorder_point)


class StockLevelModelTest(TestCase):
    """Test the StockLevel model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.warehouse = Warehouse.objects.create(
            organization=self.org, name="WH", code="WH-SL"
        )
        self.item = InventoryItem.objects.create(
            organization=self.org, sku="SL-001", name="Part X"
        )
        self.stock = StockLevel.objects.create(
            item=self.item,
            warehouse=self.warehouse,
            quantity=Decimal("200"),
            reserved_quantity=Decimal("50"),
        )

    def test_available_quantity(self):
        self.assertEqual(self.stock.available_quantity, Decimal("150"))

    def test_available_quantity_over_reserved(self):
        self.stock.reserved_quantity = Decimal("300")
        self.assertEqual(self.stock.available_quantity, 0)

    def test_str_representation(self):
        self.assertIn("SL-001", str(self.stock))
        self.assertIn("WH-SL", str(self.stock))


class StockServiceTest(TestCase):
    """Test the StockService."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.wh1 = Warehouse.objects.create(
            organization=self.org, name="WH1", code="WH-S1"
        )
        self.wh2 = Warehouse.objects.create(
            organization=self.org, name="WH2", code="WH-S2"
        )
        self.item = InventoryItem.objects.create(
            organization=self.org, sku="SVC-001", name="Service Part"
        )
        StockLevel.objects.create(
            item=self.item, warehouse=self.wh1, quantity=Decimal("500")
        )

    def test_receive_stock(self):
        stock = StockService.receive_stock(
            self.item, self.wh1, Decimal("100"), reference="PO-001"
        )
        self.assertEqual(stock.quantity, Decimal("600"))
        self.assertIsNotNone(stock.last_received_at)

    def test_receive_stock_negative_raises(self):
        with self.assertRaises(ValueError):
            StockService.receive_stock(self.item, self.wh1, Decimal("-10"))

    def test_reserve_stock(self):
        stock = StockService.reserve_stock(self.item, self.wh1, Decimal("100"))
        self.assertEqual(stock.reserved_quantity, Decimal("100"))

    def test_reserve_stock_insufficient_raises(self):
        with self.assertRaises(ValueError):
            StockService.reserve_stock(self.item, self.wh1, Decimal("600"))

    def test_release_reservation(self):
        StockService.reserve_stock(self.item, self.wh1, Decimal("200"))
        stock = StockService.release_reservation(self.item, self.wh1, Decimal("100"))
        self.assertEqual(stock.reserved_quantity, Decimal("100"))

    def test_transfer_stock(self):
        source, dest = StockService.transfer_stock(
            self.item, self.wh1, self.wh2, Decimal("150")
        )
        self.assertEqual(source.quantity, Decimal("350"))
        self.assertEqual(dest.quantity, Decimal("150"))

    def test_transfer_stock_same_warehouse_raises(self):
        with self.assertRaises(ValueError):
            StockService.transfer_stock(self.item, self.wh1, self.wh1, Decimal("10"))

    def test_cycle_count(self):
        stock = StockService.cycle_count(self.item, self.wh1, Decimal("480"))
        self.assertEqual(stock.quantity, Decimal("480"))
        self.assertIsNotNone(stock.last_counted_at)


class InventoryAPITest(TestCase):
    """Test inventory API endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass12345",
            first_name="Test",
            last_name="User",
            organization=self.org,
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.warehouse = Warehouse.objects.create(
            organization=self.org, name="API Warehouse", code="WH-API"
        )
        self.item = InventoryItem.objects.create(
            organization=self.org,
            sku="API-001",
            name="API Widget",
            unit_cost=Decimal("25.00"),
            reorder_point=Decimal("50"),
        )
        StockLevel.objects.create(
            item=self.item, warehouse=self.warehouse, quantity=Decimal("200")
        )

    def test_list_items(self):
        response = self.client.get("/api/inventory/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_item(self):
        response = self.client.get(f"/api/inventory/items/{self.item.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], "API-001")

    def test_low_stock_endpoint(self):
        # Set stock below reorder point
        StockLevel.objects.filter(item=self.item).update(quantity=Decimal("10"))
        response = self.client.get("/api/inventory/items/low_stock/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_adjust_stock(self):
        response = self.client.post(
            f"/api/inventory/items/{self.item.id}/adjust_stock/",
            {
                "warehouse_id": str(self.warehouse.id),
                "quantity_change": "50",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Decimal(response.data["quantity"]),
            Decimal("250"),
        )

    def test_list_warehouses(self):
        response = self.client.get("/api/inventory/warehouses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
