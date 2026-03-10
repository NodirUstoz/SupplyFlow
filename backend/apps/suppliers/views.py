"""
Supplier views.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Contract, Supplier, SupplierContact, SupplierRating
from .serializers import (
    ContractSerializer,
    SupplierContactSerializer,
    SupplierDetailSerializer,
    SupplierListSerializer,
    SupplierRatingSerializer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    CRUD for suppliers, scoped to the user's organization.
    """

    filterset_fields = ["status", "category", "country", "currency"]
    search_fields = ["name", "code", "email", "city"]
    ordering_fields = ["name", "overall_score", "lead_time_days", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Supplier.objects.select_related("created_by", "organization")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return SupplierListSerializer
        return SupplierDetailSerializer

    def get_permissions(self):
        if self.action in ("destroy",):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get", "post"])
    def contacts(self, request, pk=None):
        supplier = self.get_object()
        if request.method == "GET":
            contacts = supplier.contacts.all()
            serializer = SupplierContactSerializer(contacts, many=True)
            return Response(serializer.data)
        serializer = SupplierContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=supplier)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def ratings(self, request, pk=None):
        supplier = self.get_object()
        if request.method == "GET":
            ratings = supplier.ratings.all()
            serializer = SupplierRatingSerializer(ratings, many=True)
            return Response(serializer.data)
        serializer = SupplierRatingSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=supplier)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def performance(self, request, pk=None):
        """Aggregate performance data for a supplier."""
        supplier = self.get_object()
        ratings = supplier.ratings.values("dimension").annotate(
            avg_score=models.Avg("score"),
            latest_score=models.Subquery(
                SupplierRating.objects.filter(
                    supplier=supplier,
                    dimension=models.OuterRef("dimension"),
                )
                .order_by("-period_end")
                .values("score")[:1]
            ),
        )

        from django.db.models import Avg, Count
        order_stats = supplier.purchase_orders.aggregate(
            total_orders=Count("id"),
            avg_lead_time=Avg("actual_lead_time_days"),
        )

        return Response(
            {
                "supplier_id": str(supplier.id),
                "overall_score": float(supplier.overall_score),
                "ratings_by_dimension": list(ratings),
                "order_statistics": order_stats,
            }
        )


class SupplierContactViewSet(viewsets.ModelViewSet):
    """Standalone CRUD for supplier contacts."""

    serializer_class = SupplierContactSerializer
    filterset_fields = ["supplier", "is_primary"]
    search_fields = ["first_name", "last_name", "email"]

    def get_queryset(self):
        user = self.request.user
        qs = SupplierContact.objects.select_related("supplier")
        if not user.is_superuser:
            qs = qs.filter(supplier__organization=user.organization)
        return qs


class ContractViewSet(viewsets.ModelViewSet):
    """CRUD for supplier contracts."""

    serializer_class = ContractSerializer
    filterset_fields = ["supplier", "status"]
    search_fields = ["contract_number", "title"]
    ordering_fields = ["start_date", "end_date", "total_value"]

    def get_queryset(self):
        user = self.request.user
        qs = Contract.objects.select_related("supplier", "created_by")
        if not user.is_superuser:
            qs = qs.filter(supplier__organization=user.organization)
        return qs


# Import models for the performance action
from django.db import models
