"""
Procurement URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"requisitions", views.PurchaseRequisitionViewSet, basename="requisition")
router.register(r"orders", views.PurchaseOrderViewSet, basename="purchase-order")
router.register(r"order-lines", views.PurchaseOrderLineViewSet, basename="po-line")
router.register(r"approvals", views.ApprovalWorkflowViewSet, basename="approval")

urlpatterns = [
    path("", include(router.urls)),
]
