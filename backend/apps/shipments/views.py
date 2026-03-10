"""
Shipment views.
"""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Carrier, Shipment, ShipmentItem, ShipmentTracking
from .serializers import (
    CarrierSerializer,
    ShipmentDetailSerializer,
    ShipmentItemSerializer,
    ShipmentListSerializer,
    ShipmentTrackingSerializer,
)


class CarrierViewSet(viewsets.ModelViewSet):
    """CRUD for shipping carriers."""

    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]


class ShipmentViewSet(viewsets.ModelViewSet):
    """CRUD for shipments with tracking capabilities."""

    filterset_fields = ["status", "shipment_type", "carrier", "purchase_order"]
    search_fields = ["shipment_number", "tracking_number"]
    ordering_fields = ["created_at", "estimated_arrival", "actual_arrival", "shipping_cost"]

    def get_queryset(self):
        user = self.request.user
        qs = Shipment.objects.select_related(
            "carrier", "purchase_order", "created_by", "organization"
        ).prefetch_related("items", "tracking_events")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ShipmentListSerializer
        return ShipmentDetailSerializer

    @action(detail=True, methods=["get", "post"])
    def tracking(self, request, pk=None):
        """View or add tracking events to a shipment."""
        shipment = self.get_object()
        if request.method == "GET":
            events = shipment.tracking_events.all()
            serializer = ShipmentTrackingSerializer(events, many=True)
            return Response(serializer.data)

        serializer = ShipmentTrackingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(shipment=shipment)

        # Update shipment status to match latest tracking event
        shipment.status = event.status
        update_fields = ["status", "updated_at"]

        if event.status == Shipment.Status.PICKED_UP and not shipment.actual_departure:
            shipment.actual_departure = event.event_time
            update_fields.append("actual_departure")
        elif event.status == Shipment.Status.DELIVERED and not shipment.actual_arrival:
            shipment.actual_arrival = event.event_time
            update_fields.append("actual_arrival")

        shipment.save(update_fields=update_fields)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """Return tracking event coordinates for map visualization."""
        shipment = self.get_object()
        events = (
            shipment.tracking_events
            .exclude(latitude__isnull=True)
            .order_by("event_time")
            .values("latitude", "longitude", "location", "event_time", "status")
        )
        route_data = {
            "shipment_id": str(shipment.id),
            "origin": {
                "lat": float(shipment.origin_latitude) if shipment.origin_latitude else None,
                "lng": float(shipment.origin_longitude) if shipment.origin_longitude else None,
                "address": shipment.origin_address,
            },
            "destination": {
                "lat": float(shipment.destination_latitude) if shipment.destination_latitude else None,
                "lng": float(shipment.destination_longitude) if shipment.destination_longitude else None,
                "address": shipment.destination_address,
            },
            "waypoints": list(events),
        }
        return Response(route_data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """List only in-transit shipments."""
        active_statuses = [
            Shipment.Status.PICKED_UP,
            Shipment.Status.IN_TRANSIT,
            Shipment.Status.CUSTOMS,
            Shipment.Status.OUT_FOR_DELIVERY,
        ]
        qs = self.get_queryset().filter(status__in=active_statuses)
        serializer = ShipmentListSerializer(qs, many=True)
        return Response(serializer.data)


class ShipmentItemViewSet(viewsets.ModelViewSet):
    """CRUD for shipment items."""

    serializer_class = ShipmentItemSerializer
    filterset_fields = ["shipment"]

    def get_queryset(self):
        user = self.request.user
        qs = ShipmentItem.objects.select_related("shipment")
        if not user.is_superuser:
            qs = qs.filter(shipment__organization=user.organization)
        return qs
