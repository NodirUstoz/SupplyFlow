"""
Celery tasks for shipment tracking and notifications.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def poll_carrier_updates(self):
    """
    Poll carrier APIs for shipment status updates.
    Runs every 15 minutes via Celery Beat.
    """
    from .models import Shipment, ShipmentTracking

    active_statuses = [
        Shipment.Status.PICKED_UP,
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.CUSTOMS,
        Shipment.Status.OUT_FOR_DELIVERY,
    ]

    active_shipments = Shipment.objects.filter(
        status__in=active_statuses,
        tracking_number__isnull=False,
    ).exclude(tracking_number="").select_related("carrier")

    updated_count = 0
    for shipment in active_shipments:
        try:
            new_status = _fetch_carrier_status(shipment)
            if new_status and new_status != shipment.status:
                ShipmentTracking.objects.create(
                    shipment=shipment,
                    status=new_status,
                    description=f"Auto-updated from carrier API ({shipment.carrier.name})",
                    event_time=timezone.now(),
                )
                shipment.status = new_status
                update_fields = ["status", "updated_at"]

                if new_status == Shipment.Status.DELIVERED:
                    shipment.actual_arrival = timezone.now()
                    update_fields.append("actual_arrival")

                shipment.save(update_fields=update_fields)
                updated_count += 1
        except Exception as exc:
            logger.warning(
                "Failed to poll carrier for shipment %s: %s",
                shipment.shipment_number,
                str(exc),
            )

    logger.info("Carrier polling complete: %d shipments updated", updated_count)
    return {"updated": updated_count, "total_checked": active_shipments.count()}


def _fetch_carrier_status(shipment):
    """
    Placeholder for carrier API integration.

    In production, implement per-carrier API calls here using the
    carrier.code to dispatch to the right integration module.
    Returns a Shipment.Status value or None if no update.
    """
    # Example stub -- replace with real carrier API integration:
    # if shipment.carrier.code == 'FEDEX':
    #     return fedex_client.track(shipment.tracking_number)
    # elif shipment.carrier.code == 'DHL':
    #     return dhl_client.track(shipment.tracking_number)
    return None


@shared_task
def send_shipment_notification(shipment_id: str, event_type: str):
    """
    Send email/webhook notification for shipment status changes.
    """
    from .models import Shipment

    try:
        shipment = Shipment.objects.select_related(
            "organization", "carrier", "created_by"
        ).get(id=shipment_id)
    except Shipment.DoesNotExist:
        logger.error("Shipment %s not found for notification", shipment_id)
        return

    logger.info(
        "Sending %s notification for shipment %s to org %s",
        event_type,
        shipment.shipment_number,
        shipment.organization.name,
    )

    # In production, send email or webhook:
    # from django.core.mail import send_mail
    # send_mail(
    #     subject=f"Shipment {shipment.shipment_number} - {event_type}",
    #     message=f"Status: {shipment.get_status_display()}",
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     recipient_list=[shipment.created_by.email],
    # )


@shared_task
def check_overdue_shipments():
    """Flag shipments that have exceeded their estimated arrival time."""
    from .models import Shipment

    now = timezone.now()
    overdue = Shipment.objects.filter(
        estimated_arrival__lt=now,
        actual_arrival__isnull=True,
        status__in=[
            Shipment.Status.PICKED_UP,
            Shipment.Status.IN_TRANSIT,
            Shipment.Status.CUSTOMS,
        ],
    )

    count = overdue.count()
    if count > 0:
        logger.warning("%d overdue shipments detected", count)
        for shipment in overdue[:50]:
            send_shipment_notification.delay(
                str(shipment.id), "overdue"
            )

    return {"overdue_count": count}
