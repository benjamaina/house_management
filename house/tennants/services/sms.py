from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
import logging
import os
from twilio.http.http_client import TwilioHttpClient

logger = logging.getLogger(__name__)

proxy_client = TwilioHttpClient(
    proxy={'http': os.environ.get('HTTP_PROXY'), 'https': os.environ.get('HTTP_PROXY')}
)

client = Client(
    settings.TWILIO_ACCOUNT_SID,
    settings.TWILIO_AUTH_TOKEN,
    http_client=proxy_client
)

class TwilioNotificationService:
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.from_number = settings.TWILIO_PHONE_NUMBER
    
    def send_sms(self, to_number, message):
        """Send SMS via Twilio"""
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=str(to_number)
            )
            logger.info(f"SMS sent successfully to {to_number}. SID: {msg.sid}")
            return True, msg.sid
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return False, str(e)
    
    def send_rent_due_reminder(self, rent_charge):
        """Send rent due reminder"""
        tenant = rent_charge.tenant
        
        if not tenant.sms_notifications:
            logger.info(f"SMS notifications disabled for {tenant.full_name}")
            return False, "Notifications disabled"
        
        days_until_due = (tenant.rent_due_date - timezone.now().date()).days
        message = self._generate_rent_reminder(rent_charge, days_until_due)
        
        success, result = self.send_sms(tenant.phone, message)
        
        if success:
            rent_charge.reminder_sent = True
            rent_charge.reminder_sent_at = timezone.now()
            rent_charge.save(update_fields=['reminder_sent', 'reminder_sent_at'])
            
            tenant.last_reminder_sent = timezone.now()
            tenant.save(update_fields=['last_reminder_sent'])
        
        return success, result
    
    def send_payment_confirmation(self, payment):
        """Send payment confirmation"""
        tenant = payment.tenant
        
        if not tenant.sms_notifications:
            return False, "Notifications disabled"
        
        message = self._generate_payment_confirmation(payment)
        return self.send_sms(tenant.phone, message)
    
    def send_move_in_welcome(self, tenant):
        """Send welcome message when tenant moves in"""
        if not tenant.sms_notifications:
            return False, "Notifications disabled"
        
        message = self._generate_welcome_message(tenant)
        return self.send_sms(tenant.phone, message)
    
    def send_overdue_notice(self, rent_charge):
        """Send overdue payment notice"""
        tenant = rent_charge.tenant
        
        if not tenant.sms_notifications_enabled:
            return False, "Notifications disabled"
        
        message = self._generate_overdue_notice(rent_charge)
        return self.send_sms(tenant.phone, message)
    
    def _generate_rent_reminder(self, rent_charge, days_until_due):
        """Generate rent reminder message"""
        tenant = rent_charge.tenant
        
        if days_until_due <= 0:
            urgency = "TODAY"
        elif days_until_due == 1:
            urgency = "TOMORROW"
        else:
            urgency = f"in {days_until_due} days"
        
        message = (
            f"Hi {tenant.full_name},\n\n"
            f"Rent Reminder: Your rent of KES {rent_charge.amount_due:,.2f} "
            f"for {tenant.building_name} - House {tenant.house.house_number} "
            f"is due {urgency} ({tenant.rent_due_date.strftime('%d %b %Y')}).\n\n"
        )
        
        if rent_charge.balance > 0:
            message += f"Current balance: KES {rent_charge.balance:,.2f}\n\n"
        
        message += "Thank you for your prompt payment!"
        
        return message
    
    def _generate_payment_confirmation(self, payment):
        """Generate payment confirmation message"""
        tenant = payment.tenant
        rent_charge = payment.rent_charge
        
        message = (
            f"Hi {tenant.full_name},\n\n"
            f"Payment Received: KES {payment.amount:,.2f} "
            f"for {rent_charge.get_month_display()} {rent_charge.year} rent.\n\n"
            f"Payment Method: {payment.get_payment_method_display()}\n"
            f"Date: {payment.paid_at.strftime('%d %b %Y, %I:%M %p')}\n\n"
        )
        
        if rent_charge.balance > 0:
            message += f"Remaining balance: KES {rent_charge.balance:,.2f}\n\n"
        else:
            message += "Your rent is now fully paid. Thank you!\n\n"
        
        return message
    
    def _generate_welcome_message(self, tenant):
        """Generate welcome message for new tenant"""
        message = (
            f"Welcome {tenant.full_name}!\n\n"
            f"You've been assigned to {tenant.building_name} - "
            f"House {tenant.house.house_number}.\n\n"
            f"Monthly Rent: KES {tenant.rent:,.2f}\n"
            f"Rent Due Date: {tenant.rent_due_date.strftime('%d of each month')}\n\n"
            f"We're happy to have you!"
        )
        return message
    
    def _generate_overdue_notice(self, rent_charge):
        """Generate overdue payment notice"""
        tenant = rent_charge.tenant
        days_overdue = (timezone.now().date() - tenant.rent_due_date).days
        
        message = (
            f"Hi {tenant.full_name},\n\n"
            f"OVERDUE NOTICE: Your rent payment for "
            f"{rent_charge.get_month_display()} {rent_charge.year} "
            f"is {days_overdue} days overdue.\n\n"
            f"Amount Due: KES {rent_charge.balance:,.2f}\n"
            f"Due Date: {tenant.rent_due_date.strftime('%d %b %Y')}\n\n"
            f"Please make payment as soon as possible.\n"
            f"Contact us if you need assistance."
        )
        return message