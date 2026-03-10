"""
Admin configuration for analytics app.
"""

from django.contrib import admin

from .models import AlertEvent, AlertRule, DashboardMetricSnapshot, KPITarget


@admin.register(DashboardMetricSnapshot)
class DashboardMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("metric_name", "value", "snapshot_date", "organization")
    list_filter = ("metric_name", "organization")
    ordering = ("-snapshot_date",)
    readonly_fields = ("created_at",)


@admin.register(KPITarget)
class KPITargetAdmin(admin.ModelAdmin):
    list_display = ("metric_name", "target_value", "direction", "is_active", "organization")
    list_filter = ("metric_name", "is_active", "direction")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rule_type", "channel", "is_active", "organization")
    list_filter = ("rule_type", "channel", "is_active")
    search_fields = ("name",)
    filter_horizontal = ("recipients",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "rule", "is_read", "created_at")
    list_filter = ("severity", "is_read", "rule__rule_type")
    search_fields = ("title", "message")
    readonly_fields = ("created_at",)
