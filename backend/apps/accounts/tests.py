"""
Tests for accounts app: models and API endpoints.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import Organization, User


class OrganizationModelTest(TestCase):
    """Test Organization model."""

    def setUp(self):
        self.org = Organization.objects.create(
            name="Acme Manufacturing",
            slug="acme-manufacturing",
            city="Dallas",
            country="US",
        )

    def test_str_representation(self):
        self.assertEqual(str(self.org), "Acme Manufacturing")

    def test_default_is_active(self):
        self.assertTrue(self.org.is_active)


class UserModelTest(TestCase):
    """Test custom User model."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="john@example.com",
            password="securepass123",
            first_name="John",
            last_name="Smith",
            organization=self.org,
            role=User.Role.BUYER,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.user), "John Smith (john@example.com)")

    def test_full_name(self):
        self.assertEqual(self.user.full_name, "John Smith")

    def test_email_is_username(self):
        self.assertEqual(self.user.email, "john@example.com")
        self.assertIsNone(self.user.username)

    def test_is_admin_false_for_buyer(self):
        self.assertFalse(self.user.is_admin)

    def test_is_admin_true_for_admin_role(self):
        self.user.role = User.Role.ADMIN
        self.assertTrue(self.user.is_admin)

    def test_is_manager_for_manager_role(self):
        self.user.role = User.Role.MANAGER
        self.assertTrue(self.user.is_manager)

    def test_can_approve(self):
        self.user.role = User.Role.MANAGER
        self.assertTrue(self.user.can_approve)

    def test_viewer_cannot_approve(self):
        self.user.role = User.Role.VIEWER
        self.assertFalse(self.user.can_approve)


class UserManagerTest(TestCase):
    """Test custom UserManager."""

    def test_create_user(self):
        user = User.objects.create_user(
            email="basic@example.com",
            password="pass1234567",
            first_name="Basic",
            last_name="User",
        )
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("pass1234567"))

    def test_create_user_no_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass1234567")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="admin1234567",
            first_name="Admin",
            last_name="User",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)


class AuthAPITest(TestCase):
    """Test authentication API endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.user = User.objects.create_user(
            email="auth@example.com",
            password="testpass12345",
            first_name="Auth",
            last_name="User",
            organization=self.org,
        )
        self.client = APIClient()

    def test_login_success(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "auth@example.com", "password": "testpass12345"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)

    def test_login_wrong_password(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "auth@example.com", "password": "wrongpass"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "auth@example.com")

    def test_profile_unauthenticated(self):
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "testpass12345",
                "new_password": "newpass1234567",
                "new_password_confirm": "newpass1234567",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass1234567"))


class UserViewSetAPITest(TestCase):
    """Test user management API endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="TestOrg", slug="testorg")
        self.admin = User.objects.create_user(
            email="admin-api@example.com",
            password="testpass12345",
            first_name="Admin",
            last_name="API",
            organization=self.org,
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="testpass12345",
            first_name="Viewer",
            last_name="User",
            organization=self.org,
            role=User.Role.VIEWER,
        )
        self.client = APIClient()

    def test_list_users_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_users_as_viewer(self):
        self.client.force_authenticate(user=self.viewer)
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
