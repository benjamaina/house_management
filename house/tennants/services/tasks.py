from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from tennants.models import RentCharge, Tenant
from .sms import TwilioNotificationService
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_daily_rent_reminders():
    """
    Daily task to check and send rent reminders
    Runs every day to check for upcoming rent due dates
    """
    notification_service = TwilioNotificationService()
    today = timezone.now().date()
    sent_count = 0
    
    # Get all active tenants
    active_tenants = Tenant.objects.filter(is_active=True, sms_notifications_enabled=True)
    
    for tenant in active_tenants:
        days_until_due = (tenant.rent_due_date - today).days
        
        # Check if reminder should be sent
        if days_until_due == tenant.reminder_days_before or days_until_due == 0:
            # Find the current rent charge for this tenant
            current_month = today.month
            current_year = today.year
            
            try:
                rent_charge = RentCharge.objects.get(
                    tenant=tenant,
                    year=current_year,
                    month=current_month
                )
                
                # Only send if not already sent
                if not rent_charge.reminder_sent:
                    success, result = notification_service.send_rent_due_reminder(rent_charge)
                    if success:
                        sent_count += 1
                        logger.info(f"Reminder sent to {tenant.full_name}")
                    
            except RentCharge.DoesNotExist:
                logger.warning(f"No rent charge found for {tenant.full_name} for {current_month}/{current_year}")
    
    logger.info(f"Daily rent reminders completed. Sent: {sent_count}")
    return f"Sent {sent_count} reminders"


@shared_task
def send_overdue_notices():
    """
    Check for overdue rent and send notices
    Run this weekly or as needed
    """
    notification_service = TwilioNotificationService()
    today = timezone.now().date()
    sent_count = 0
    
    # Get rent charges that are overdue and unpaid
    overdue_charges = RentCharge.objects.filter(
        tenant__is_active=True,
        tenant__sms_notifications_enabled=True,
        tenant__rent_due_date__lt=today
    ).exclude(
        balance__lte=0  # Exclude fully paid
    )
    
    for rent_charge in overdue_charges:
        # Send overdue notice
        success, result = notification_service.send_overdue_notice(rent_charge)
        if success:
            sent_count += 1
            logger.info(f"Overdue notice sent to {rent_charge.tenant.full_name}")
    
    logger.info(f"Overdue notices completed. Sent: {sent_count}")
    return f"Sent {sent_count} overdue notices"