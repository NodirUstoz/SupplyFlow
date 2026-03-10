"""
Account serializers for User and Organization.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Organization

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "address", "city", "state", "country",
            "postal_code", "phone", "website", "logo", "is_active",
            "member_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class UserSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "role",
            "organization", "organization_name", "phone", "job_title",
            "avatar", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=10)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "password",
            "password_confirm", "role", "organization", "phone", "job_title",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        if data["password"] != data.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for the authenticated user's own profile."""

    organization_detail = OrganizationSerializer(source="organization", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "role",
            "organization", "organization_detail", "phone", "job_title",
            "avatar", "is_active", "created_at",
        ]
        read_only_fields = ["id", "email", "role", "organization", "is_active", "created_at"]


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=10)
    new_password_confirm = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT token serializer that includes user metadata in the response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "role": self.user.role,
            "organization_id": str(self.user.organization_id) if self.user.organization_id else None,
        }
        return data
