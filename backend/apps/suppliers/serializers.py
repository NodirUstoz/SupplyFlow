"""
Supplier serializers.
"""

from rest_framework import serializers

from .models import Contract, Supplier, SupplierContact, SupplierRating


class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = [
            "id", "supplier", "first_name", "last_name", "email",
            "phone", "job_title", "is_primary", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SupplierRatingSerializer(serializers.ModelSerializer):
    rated_by_name = serializers.CharField(source="rated_by.full_name", read_only=True)

    class Meta:
        model = SupplierRating
        fields = [
            "id", "supplier", "dimension", "score", "period_start",
            "period_end", "comments", "rated_by", "rated_by_name", "created_at",
        ]
        read_only_fields = ["id", "rated_by", "created_at"]

    def create(self, validated_data):
        validated_data["rated_by"] = self.context["request"].user
        return super().create(validated_data)


class ContractSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id", "supplier", "supplier_name", "contract_number", "title",
            "status", "start_date", "end_date", "total_value", "currency",
            "terms", "document", "auto_renew", "renewal_notice_days",
            "is_expired", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class SupplierListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    contact_count = serializers.SerializerMethodField()
    active_contracts = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            "id", "name", "code", "category", "status", "country",
            "payment_terms", "lead_time_days", "overall_score",
            "contact_count", "active_contracts", "created_at",
        ]

    def get_contact_count(self, obj):
        return obj.contacts.count()

    def get_active_contracts(self, obj):
        return obj.contracts.filter(status="active").count()


class SupplierDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail / create / update."""

    contacts = SupplierContactSerializer(many=True, read_only=True)
    ratings = SupplierRatingSerializer(many=True, read_only=True)
    contracts = ContractSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id", "organization", "name", "code", "category", "status",
            "tax_id", "website", "email", "phone", "address_line1",
            "address_line2", "city", "state", "country", "postal_code",
            "payment_terms", "currency", "lead_time_days", "notes",
            "overall_score", "contacts", "ratings", "contracts",
            "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_at", "updated_at", "overall_score"]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["organization"] = user.organization
        validated_data["created_by"] = user
        return super().create(validated_data)
