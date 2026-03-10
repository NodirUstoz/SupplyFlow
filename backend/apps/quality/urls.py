"""
Quality URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"inspections", views.QualityInspectionViewSet, basename="inspection")
router.register(r"inspection-items", views.InspectionItemViewSet, basename="inspection-item")
router.register(r"defects", views.DefectReportViewSet, basename="defect-report")

urlpatterns = [
    path("", include(router.urls)),
]
