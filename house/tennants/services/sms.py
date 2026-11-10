import logging
import os
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

logger = logging.getLogger(__name__)


def reminder_candidates(tenants, today=None):
    """
    Return [(tenant, rent_charge, days_until_due)] for unsent reminders whose due
    date falls inside the tenant's reminder window. Looks at this month's AND
    next month's charges so month-end due dates aren't missed.
    """
    from tennants.models import RentCharge  # local import avoids a circular import

    today = today or timezone.localdate()
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    periods = Q(year=today.year, month=today.month) | Q(year=next_month.year, month=next_month.month)

    charges = (
        RentCharge.objects.filter(periods, tenant__in=tenants, reminder_sent=False)
        .select_related("tenant__house__flat_building")
    )
    results = []
    for charge in charges:
        tenant = charge.tenant
        days = (tenant.due_date_for(charge.year, charge.month) - today).days
        if 0 <= days <= tenant.reminder_days_before:
            results.append((tenant, charge, days))
    return results


class TwilioNotificationService:
    def __init__(self):
        self._client = None
        self.from_number = settings.TWILIO_PHONE_NUMBER

    @property
    def client(self):
        if self._client is None:
            proxy = os.environ.get("HTTP_PROXY")   # PythonAnywhere free tier needs this
            http_client = TwilioHttpClient(
                timeout=10,
                proxy={"http": proxy, "https": proxy} if proxy else None,
            )
            self._client = Client(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, http_client=http_client
            )
        return self._client

    def send_sms(self, to_number, message):
        if not getattr(settings, "SMS_ENABLED", True):
            logger.info("SMS disabled; would send to %s: %s", to_number, message)
            return True, "sms-disabled"
        try:
            msg = self.client.messages.create(body=message, from_=self.from_number, to=str(to_number))
            logger.info("SMS sent to %s. SID: %s", to_number, msg.sid)
            return True, msg.sid
        except Exception as e:
            logger.error("Failed to send SMS to %s: %s", to_number, e)
            return False, str(e)

    # ---- senders ----------------------------------------------------------

    def send_rent_due_reminder(self, rent_charge):
        tenant = rent_charge.tenant
        if not tenant.sms_notifications:
            return False, "Notifications disabled"

        due = tenant.due_date_for(rent_charge.year, rent_charge.month)
        days_until_due = (due - timezone.localdate()).days
        message = self._generate_rent_reminder(rent_charge, days_until_due, due)

        success, result = self.send_sms(tenant.phone, message)
        if success:
            now = timezone.now()
            # .update() avoids save() -> full_clean() -> signals
            type(rent_charge).objects.filter(pk=rent_charge.pk).update(
                reminder_sent=True, reminder_sent_at=now
            )
            type(tenant).objects.filter(pk=tenant.pk).update(last_reminder_sent=now)
            rent_charge.reminder_sent = True
            rent_charge.reminder_sent_at = now
        return success, result

    def send_payment_confirmation(self, payment):
        tenant = payment.tenant
        if not tenant.sms_notifications:
            return False, "Notifications disabled"
        return self.send_sms(tenant.phone, self._generate_payment_confirmation(payment))

    def send_move_in_welcome(self, tenant):
        if not tenant.sms_notifications:
            return False, "Notifications disabled"
        return self.send_sms(tenant.phone, self._generate_welcome_message(tenant))

    def send_overdue_notice(self, rent_charge):
        tenant = rent_charge.tenant
        if not tenant.sms_notifications:
            return False, "Notifications disabled"
        success, result = self.send_sms(tenant.phone, self._generate_overdue_notice(rent_charge))
        if success:
            type(tenant).objects.filter(pk=tenant.pk).update(last_notification_sent=timezone.now())
        return success, result

    # ---- message templates ------------------------------------------------

    @staticmethod
    def _location(tenant):
        if tenant.house:
            return f"{tenant.building_name} - House {tenant.house.house_number}"
        return "your unit"

    def _generate_rent_reminder(self, rent_charge, days_until_due, due_date):
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
            f"for {self._location(tenant)} is due {urgency} ({due_date.strftime('%d %b %Y')}).\n\n"
        )
        if rent_charge.balance > 0:
            message += f"Current balance: KES {rent_charge.balance:,.2f}\n\n"
        return message + "Thank you for your prompt payment!"

    def _generate_payment_confirmation(self, payment):
        tenant = payment.tenant
        rent_charge = payment.rent_charge
        paid_local = timezone.localtime(payment.paid_at)
        message = (
            f"Hi {tenant.full_name},\n\n"
            f"Payment Received: KES {payment.amount:,.2f} "
            f"for {rent_charge.get_month_display()} {rent_charge.year} rent.\n\n"
            f"Payment Method: {payment.get_payment_method_display()}\n"
            f"Date: {paid_local.strftime('%d %b %Y, %I:%M %p')}\n\n"
        )
        if rent_charge.balance > 0:
            message += f"Remaining balance: KES {rent_charge.balance:,.2f}\n\n"
        else:
            message += "Your rent is now fully paid. Thank you!\n\n"
        return message

    def _generate_welcome_message(self, tenant):
        return (
            f"Welcome {tenant.full_name}!\n\n"
            f"You've been assigned to {self._location(tenant)}.\n\n"
            f"Monthly Rent: KES {tenant.rent:,.2f}\n"
            f"Rent due on day {tenant.rent_due_date.day} of each month\n\n"
            f"We're happy to have you!"
        )

    def _generate_overdue_notice(self, rent_charge):
        tenant = rent_charge.tenant
        due = tenant.due_date_for(rent_charge.year, rent_charge.month)
        days_overdue = (timezone.localdate() - due).days
        return (
            f"Hi {tenant.full_name},\n\n"
            f"OVERDUE NOTICE: Your rent payment for "
            f"{rent_charge.get_month_display()} {rent_charge.year} "
            f"is {days_overdue} days overdue.\n\n"
            f"Amount Due: KES {rent_charge.balance:,.2f}\n"
            f"Due Date: {due.strftime('%d %b %Y')}\n\n"
            f"Please make payment as soon as possible.\n"
            f"Contact us if you need assistance."
        )