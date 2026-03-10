"""
Shipment URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"carriers", views.CarrierViewSet, basename="carrier")
router.register(r"items", views.ShipmentItemViewSet, basename="shipment-item")
router.register(r"", views.ShipmentViewSet, basename="shipment")

urlpatterns = [
    path("", include(router.urls)),
]
