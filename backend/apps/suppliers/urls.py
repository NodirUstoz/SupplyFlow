"""
Supplier URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.SupplierViewSet, basename="supplier")
router.register(r"contacts", views.SupplierContactViewSet, basename="supplier-contact")
router.register(r"contracts", views.ContractViewSet, basename="contract")

urlpatterns = [
    path("", include(router.urls)),
]
