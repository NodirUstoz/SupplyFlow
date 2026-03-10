"""
SupplyFlow URL Configuration.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin
    path("api/admin/", admin.site.urls),
    # API schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # App endpoints
    path("api/auth/", include("apps.accounts.urls")),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/suppliers/", include("apps.suppliers.urls")),
    path("api/procurement/", include("apps.procurement.urls")),
    path("api/shipments/", include("apps.shipments.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/quality/", include("apps.quality.urls")),
    path("api/forecasting/", include("apps.forecasting.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
]

admin.site.site_header = "SupplyFlow Administration"
admin.site.site_title = "SupplyFlow Admin"
admin.site.index_title = "Supply Chain Management"
