"""
Analytics URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"snapshots", views.MetricSnapshotViewSet, basename="metric-snapshot")
router.register(r"kpi-targets", views.KPITargetViewSet, basename="kpi-target")
router.register(r"alert-rules", views.AlertRuleViewSet, basename="alert-rule")
router.register(r"alerts", views.AlertEventViewSet, basename="alert-event")

urlpatterns = [
    path("dashboard/", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("", include(router.urls)),
]
