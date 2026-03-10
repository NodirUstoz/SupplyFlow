"""
Analytics serializers.
"""

from rest_framework import serializers

from .models import AlertEvent, AlertRule, DashboardMetricSnapshot, KPITarget


class DashboardMetricSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardMetricSnapshot
        fields = [
            "id", "organization", "metric_name", "value",
            "snapshot_date", "metadata", "created_at",
        ]
        read_only_fields = ["id", "organization", "created_at"]

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user.organization
        return super().create(validated_data)


class KPITargetSerializer(serializers.ModelSerializer):
    is_breached = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = KPITarget
        fields = [
            "id", "organization", "metric_name", "target_value",
            "direction", "is_active", "is_breached",
            "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at"]

    def get_is_breached(self, obj):
        """Check against the most recent snapshot for this metric."""
        latest = DashboardMetricSnapshot.objects.filter(
            organization=obj.organization,
            metric_name=obj.metric_name,
        ).order_by("-snapshot_date").first()
        if latest is None:
            return None
        return obj.is_breached(latest.value)

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["created_by"] = user
        return super().create(validated_data)


class AlertRuleSerializer(serializers.ModelSerializer):
    event_count = serializers.SerializerMethodField()

    class Meta:
        model = AlertRule
        fields = [
            "id", "organization", "name", "rule_type", "is_active",
            "channel", "recipients", "config", "event_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def get_event_count(self, obj):
        return obj.events.count()

    def create(self, validated_data):
        validated_data["organization"] = self.context["request"].user.organization
        return super().create(validated_data)


class AlertEventSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    read_by_name = serializers.CharField(
        source="read_by.full_name", read_only=True, default=None
    )

    class Meta:
        model = AlertEvent
        fields = [
            "id", "organization", "rule", "rule_name", "severity",
            "title", "message", "related_object_type", "related_object_id",
            "is_read", "read_by", "read_by_name", "read_at", "created_at",
        ]
        read_only_fields = [
            "id", "organization", "rule", "severity", "title", "message",
            "related_object_type", "related_object_id", "created_at",
        ]


class DashboardSummarySerializer(serializers.Serializer):
    """Read-only serializer for the combined dashboard overview endpoint."""

    total_po_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    open_po_count = serializers.IntegerField()
    inventory_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    low_stock_count = serializers.IntegerField()
    active_shipments = serializers.IntegerField()
    on_time_delivery_rate = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    avg_supplier_score = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    pending_approvals = serializers.IntegerField()
    unread_alerts = serializers.IntegerField()
