"""
Admin configuration for quality app.
"""

from django.contrib import admin

from .models import DefectReport, InspectionItem, QualityInspection


class InspectionItemInline(admin.TabularInline):
    model = InspectionItem
    extra = 0
    fields = (
        "item_code", "description", "quantity_inspected",
        "quantity_accepted", "quantity_rejected", "result",
    )


class DefectReportInline(admin.StackedInline):
    model = DefectReport
    extra = 0
    fields = (
        "defect_code", "title", "severity", "quantity_affected",
        "disposition", "resolved",
    )


@admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "inspection_number", "inspection_type", "status",
        "supplier", "inspector", "inspection_date",
        "overall_score", "defects_found",
    )
    list_filter = ("status", "inspection_type", "organization")
    search_fields = ("inspection_number",)
    inlines = [InspectionItemInline, DefectReportInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(InspectionItem)
class InspectionItemAdmin(admin.ModelAdmin):
    list_display = (
        "item_code", "inspection", "quantity_inspected",
        "quantity_accepted", "quantity_rejected", "result",
    )
    list_filter = ("result",)


@admin.register(DefectReport)
class DefectReportAdmin(admin.ModelAdmin):
    list_display = (
        "defect_code", "title", "severity", "disposition",
        "resolved", "reported_by", "created_at",
    )
    list_filter = ("severity", "disposition", "resolved")
    search_fields = ("defect_code", "title")
