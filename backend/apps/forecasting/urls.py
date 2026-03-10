"""
Forecasting URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"forecasts", views.DemandForecastViewSet, basename="demand-forecast")
router.register(r"accuracy", views.ForecastAccuracyViewSet, basename="forecast-accuracy")

urlpatterns = [
    path("config/", views.ForecastConfigurationView.as_view(), name="forecast-config"),
    path("", include(router.urls)),
]
