"""
Tests for shipments app: models and API endpoints.
"""

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User

from .models import Carrier, Shipment, ShipmentItem, ShipmentTracking


class CarrierModelTest(TestCase):
    """Test Carrier model."""

    def setUp(self):
        self.carrier = Carrier.objects.create(
            name="FedEx",
            code="FEDEX",
            tracking_url_template="https://www.fedex.com/track?trknbr={tracking_number}",
        )

    def test_str_representation(self):
        self.assertEqual(str(self.carrier), "FedEx")

    def test_get_tracking_url(self):
        url = self.carrier.get_tracking_url("123456789")
        self.assertEqual(url, "https://www.fedex.com/track?trknbr=123456789")

    def test_get_tracking_url_no_template(self):
        carrier = Carrier.objects.create(name="Custom", code="CUST")
        self.assertEqual(carrier.get_tracking_url("123"), "")


class ShipmentModelTest(TestCase):
    """Test Shipment model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.carrier = Carrier.objects.create(
            name="DHL", code="DHL",
            tracking_url_template="https://dhl.com/track/{tracking_number}",
        )
        self.user = User.objects.create_user(
            email="ship@example.com",
            password="testpass12345",
            first_name="Ship",
            last_name="User",
            organization=self.org,
        )
        self.shipment = Shipment.objects.create(
            organization=self.org,
            shipment_number="SHP-TEST-0001",
            carrier=self.carrier,
            tracking_number="DHL12345",
            created_by=self.user,
        )

    def test_str_representation(self):
        self.assertIn("SHP-TEST-0001", str(self.shipment))

    def test_tracking_url(self):
        self.assertEqual(self.shipment.tracking_url, "https://dhl.com/track/DHL12345")

    def test_default_status(self):
        self.assertEqual(self.shipment.status, Shipment.Status.PENDING)


class ShipmentTrackingModelTest(TestCase):
    """Test ShipmentTracking model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="track@example.com",
            password="testpass12345",
            first_name="Track",
            last_name="User",
            organization=self.org,
        )
        self.shipment = Shipment.objects.create(
            organization=self.org,
            shipment_number="SHP-TRK-0001",
            created_by=self.user,
        )
        self.event = ShipmentTracking.objects.create(
            shipment=self.shipment,
            status=Shipment.Status.PICKED_UP,
            location="Dallas, TX",
            event_time=timezone.now(),
        )

    def test_str_representation(self):
        self.assertIn("SHP-TRK-0001", str(self.event))
        self.assertIn("picked_up", str(self.event))


class ShipmentAPITest(TestCase):
    """Test shipment API endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="api-ship@example.com",
            password="testpass12345",
            first_name="API",
            last_name="Ship",
            organization=self.org,
            role=User.Role.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.carrier = Carrier.objects.create(name="UPS", code="UPS")
        self.shipment = Shipment.objects.create(
            organization=self.org,
            shipment_number="SHP-API-0001",
            carrier=self.carrier,
            status=Shipment.Status.IN_TRANSIT,
            created_by=self.user,
        )

    def test_list_shipments(self):
        response = self.client.get("/api/shipments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_active_shipments(self):
        response = self.client.get("/api/shipments/active/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Our shipment is IN_TRANSIT so it should appear
        self.assertTrue(len(response.data) >= 1)

    def test_add_tracking_event(self):
        response = self.client.post(
            f"/api/shipments/{self.shipment.id}/tracking/",
            {
                "status": "out_for_delivery",
                "location": "Chicago, IL",
                "event_time": timezone.now().isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, Shipment.Status.OUT_FOR_DELIVERY)

    def test_get_tracking_events(self):
        ShipmentTracking.objects.create(
            shipment=self.shipment,
            status=Shipment.Status.PICKED_UP,
            location="New York, NY",
            event_time=timezone.now(),
        )
        response = self.client.get(f"/api/shipments/{self.shipment.id}/tracking/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_carriers(self):
        response = self.client.get("/api/shipments/carriers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
