"""
Celery tasks for analytics.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_daily_snapshots():
    """
    Generate daily metric snapshots for all active organizations.
    Scheduled to run daily at 01:00 UTC.
    """
    from .services import SnapshotService

    count = SnapshotService.generate_all()
    logger.info("Daily snapshot generation complete: %d snapshots", count)
    return {"snapshots_created": count}


@shared_task
def evaluate_kpi_alerts():
    """
    Evaluate all active KPI targets against latest snapshots and
    create alert events for breaches.
    Scheduled daily at 01:30 UTC.
    """
    from .services import AlertService

    fired = AlertService.evaluate_all()
    logger.info("KPI alert evaluation complete: %d alerts fired", fired)
    return {"alerts_fired": fired}


@shared_task
def cleanup_old_snapshots(retention_days: int = 365):
    """
    Delete metric snapshots older than the retention period.
    Runs weekly to keep database size manageable.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import DashboardMetricSnapshot

    cutoff = timezone.now().date() - timedelta(days=retention_days)
    deleted, _ = DashboardMetricSnapshot.objects.filter(
        snapshot_date__lt=cutoff
    ).delete()

    logger.info(
        "Cleaned up %d metric snapshots older than %s",
        deleted, cutoff,
    )
    return {"deleted": deleted}


@shared_task
def cleanup_old_alerts(retention_days: int = 90):
    """
    Delete read alert events older than the retention period.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .models import AlertEvent

    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted, _ = AlertEvent.objects.filter(
        is_read=True,
        created_at__lt=cutoff,
    ).delete()

    logger.info("Cleaned up %d old alert events", deleted)
    return {"deleted": deleted}
