"""
Quality views.
"""

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DefectReport, InspectionItem, QualityInspection
from .serializers import (
    DefectReportSerializer,
    InspectionItemSerializer,
    QualityInspectionDetailSerializer,
    QualityInspectionListSerializer,
)


class QualityInspectionViewSet(viewsets.ModelViewSet):
    """CRUD for quality inspections."""

    filterset_fields = ["status", "inspection_type", "supplier", "inspector"]
    search_fields = ["inspection_number", "notes"]
    ordering_fields = ["inspection_date", "overall_score", "defects_found", "created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = QualityInspection.objects.select_related(
            "inspector", "supplier", "purchase_order", "shipment", "organization"
        ).prefetch_related("items", "defect_reports")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return QualityInspectionListSerializer
        return QualityInspectionDetailSerializer

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """
        Mark an inspection as complete.

        Auto-calculates pass/fail based on defect_rate threshold.
        Threshold default: 5% defect rate => FAILED.
        """
        inspection = self.get_object()
        threshold = float(request.data.get("threshold", 5.0))

        # Count defects from inspection items
        items = inspection.items.all()
        total_inspected = sum(float(i.quantity_inspected) for i in items)
        total_rejected = sum(float(i.quantity_rejected) for i in items)

        if total_inspected > 0:
            inspection.defects_found = int(total_rejected)
            inspection.sample_size = int(total_inspected)

        defect_rate = inspection.defect_rate
        if defect_rate > threshold:
            inspection.status = QualityInspection.Status.FAILED
        elif defect_rate > 0:
            inspection.status = QualityInspection.Status.CONDITIONAL
        else:
            inspection.status = QualityInspection.Status.PASSED

        inspection.completed_at = timezone.now()
        inspection.save(update_fields=[
            "status", "defects_found", "sample_size",
            "completed_at", "updated_at",
        ])

        serializer = QualityInspectionDetailSerializer(inspection)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def supplier_quality_report(self, request):
        """
        Aggregate quality data grouped by supplier.
        Returns average score, total inspections, and defect rate per supplier.
        """
        from django.db.models import Avg, Count, Sum

        org = request.user.organization
        data = (
            QualityInspection.objects.filter(
                organization=org,
                supplier__isnull=False,
                status__in=[
                    QualityInspection.Status.PASSED,
                    QualityInspection.Status.FAILED,
                    QualityInspection.Status.CONDITIONAL,
                ],
            )
            .values("supplier__id", "supplier__name", "supplier__code")
            .annotate(
                total_inspections=Count("id"),
                avg_score=Avg("overall_score"),
                total_defects=Sum("defects_found"),
                total_samples=Sum("sample_size"),
            )
            .order_by("supplier__name")
        )

        results = []
        for row in data:
            total_samples = row["total_samples"] or 0
            total_defects = row["total_defects"] or 0
            defect_rate = round(total_defects / total_samples * 100, 2) if total_samples > 0 else 0

            results.append({
                "supplier_id": str(row["supplier__id"]),
                "supplier_name": row["supplier__name"],
                "supplier_code": row["supplier__code"],
                "total_inspections": row["total_inspections"],
                "avg_score": round(row["avg_score"], 2) if row["avg_score"] else None,
                "total_defects": total_defects,
                "total_samples": total_samples,
                "defect_rate": defect_rate,
            })

        return Response(results)


class InspectionItemViewSet(viewsets.ModelViewSet):
    """CRUD for inspection items."""

    serializer_class = InspectionItemSerializer
    filterset_fields = ["inspection", "result"]

    def get_queryset(self):
        user = self.request.user
        qs = InspectionItem.objects.select_related("inspection", "inventory_item")
        if not user.is_superuser:
            qs = qs.filter(inspection__organization=user.organization)
        return qs


class DefectReportViewSet(viewsets.ModelViewSet):
    """CRUD for defect reports."""

    serializer_class = DefectReportSerializer
    filterset_fields = ["inspection", "severity", "disposition", "resolved"]
    search_fields = ["defect_code", "title", "description"]
    ordering_fields = ["created_at", "severity"]

    def get_queryset(self):
        user = self.request.user
        qs = DefectReport.objects.select_related(
            "inspection", "inspection_item", "reported_by"
        )
        if not user.is_superuser:
            qs = qs.filter(inspection__organization=user.organization)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        """Mark a defect as resolved."""
        defect = self.get_object()
        defect.resolved = True
        defect.resolved_at = timezone.now()
        corrective_action = request.data.get("corrective_action")
        if corrective_action:
            defect.corrective_action = corrective_action
        defect.save(update_fields=[
            "resolved", "resolved_at", "corrective_action",
        ])
        return Response(DefectReportSerializer(defect).data)
