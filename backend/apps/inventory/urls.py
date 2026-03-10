"""
Inventory URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"warehouses", views.WarehouseViewSet, basename="warehouse")
router.register(r"items", views.InventoryItemViewSet, basename="inventory-item")
router.register(r"stock", views.StockLevelViewSet, basename="stock-level")

urlpatterns = [
    path("", include(router.urls)),
]
