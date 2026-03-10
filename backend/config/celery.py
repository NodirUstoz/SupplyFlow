"""
Celery application configuration for SupplyFlow.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("supplyflow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# Periodic tasks (Celery Beat)
# ---------------------------------------------------------------------------
app.conf.beat_schedule = {
    "update-shipment-statuses": {
        "task": "apps.shipments.tasks.poll_carrier_updates",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "shipments"},
    },
    "generate-daily-forecasts": {
        "task": "apps.forecasting.tasks.generate_daily_forecasts",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "analytics"},
    },
    "check-reorder-levels": {
        "task": "apps.inventory.tasks.check_reorder_levels",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "inventory"},
    },
    "compute-supplier-scores": {
        "task": "apps.suppliers.tasks.compute_supplier_scores",
        "schedule": crontab(hour=3, minute=0, day_of_week="monday"),
        "options": {"queue": "analytics"},
    },
}

app.conf.task_routes = {
    "apps.shipments.tasks.*": {"queue": "shipments"},
    "apps.forecasting.tasks.*": {"queue": "analytics"},
    "apps.inventory.tasks.*": {"queue": "inventory"},
    "apps.suppliers.tasks.*": {"queue": "analytics"},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f"Request: {self.request!r}")
