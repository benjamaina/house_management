from django.core.management.base import BaseCommand
from django.utils.timezone import now
from house_management.models import Tennant, RentPayment
from house_management.utils import send_sms_notification

class Command(BaseCommand):
    help = "Send rent payment reminders to tenants"

    def handle(self, *args, **kwargs):
        tenants = Tennant.objects.filter(is_active=True)

        for tenant in tenants:
            last_payment = RentPayment.objects.filter(tenant=tenant, is_paid=True).order_by('-date_paid').first()
            if not last_payment or (now().date() - last_payment.date_paid).days > 30:
                message = f"Dear {tenant.name}, your rent is due. Please pay to avoid penalties."
                send_sms_notification(tenant.phone, message)
                self.stdout.write(self.style.SUCCESS(f"Reminder sent to {tenant.phone}"))
