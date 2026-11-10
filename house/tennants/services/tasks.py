import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from tennants.models import RentCharge, Tenant
from .sms import TwilioNotificationService, reminder_candidates

logger = logging.getLogger(__name__)


@shared_task
def send_daily_rent_reminders():
    service = TwilioNotificationService()
    tenants = Tenant.objects.filter(is_active=True, sms_notifications=True, house__isnull=False)

    sent = 0
    for tenant, charge, days in reminder_candidates(tenants):
        success, result = service.send_rent_due_reminder(charge)
        if success:
            sent += 1
        else:
            logger.warning("Reminder to %s failed: %s", tenant.full_name, result)

    logger.info("Daily rent reminders completed. Sent: %s", sent)
    return f"Sent {sent} reminders"


@shared_task
def send_overdue_notices():
    service = TwilioNotificationService()
    now = timezone.now()
    today = timezone.localdate()
    notified = set()   # one notice per tenant per run
    sent = 0

    charges = (
        RentCharge.objects.filter(tenant__is_active=True, tenant__sms_notifications=True)
        .select_related("tenant__house__flat_building")
        .order_by("year", "month")
    )
    for charge in charges:
        tenant = charge.tenant
        if tenant.pk in notified:
            continue
        if tenant.due_date_for(charge.year, charge.month) >= today:
            continue
        if charge.balance <= 0:            # balance is a Python property, so check it here
            continue
        if tenant.last_notification_sent and (now - tenant.last_notification_sent) < timedelta(days=7):
            continue

        success, _ = service.send_overdue_notice(charge)
        notified.add(tenant.pk)
        if success:
            sent += 1

    logger.info("Overdue notices completed. Sent: %s", sent)
    return f"Sent {sent} overdue notices"