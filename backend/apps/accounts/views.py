"""
Account views for authentication, user management, and organizations.
"""

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Organization
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    OrganizationSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    UserSerializer,
)

User = get_user_model()


class IsAdminUser(permissions.BasePermission):
    """Allow access only to users with admin or manager role."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsManagerOrAdmin(permissions.BasePermission):
    """Allow access to managers and admins."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_manager


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login endpoint returning JWT tokens plus user metadata."""

    serializer_class = CustomTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for users.
    - Admin/Manager: full access within their organization.
    - Others: read-only.
    """

    serializer_class = UserSerializer
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["created_at", "first_name", "email"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.all()
        if user.organization_id:
            return User.objects.filter(organization=user.organization)
        return User.objects.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAdminUser()]
        if self.action in ("update", "partial_update"):
            return [IsManagerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        org = self.request.user.organization
        serializer.save(organization=org)


class ProfileView(generics.RetrieveUpdateAPIView):
    """Authenticated user's own profile."""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.GenericAPIView):
    """Change the authenticated user's password."""

    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response(
            {"detail": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD for organizations (admin only for writes)."""

    serializer_class = OrganizationSerializer
    filterset_fields = ["is_active", "country"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.all()
        if user.organization_id:
            return Organization.objects.filter(id=user.organization_id)
        return Organization.objects.none()

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
