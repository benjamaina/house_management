from django.conf import settings
from django.db.models.signals import post_save,post_delete,pre_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Payment, House
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from .models import Tenant, FlatBuilding, House
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
 

from django.utils import timezone
from datetime import timedelta
from .models import RentCharge, Payment, Tenant
from tennants.services.sms import TwilioNotificationService
import logging

logger = logging.getLogger(__name__)

notification_service = TwilioNotificationService()


@receiver(post_save, sender=RentCharge)
def send_rent_reminder_on_create(sender, instance, created, **kwargs):
    """
    Send rent reminder when RentCharge is created
    Checks if reminder should be sent based on tenant's preference
    """
    if created and instance.tenant.is_active:
        tenant = instance.tenant
        days_until_due = (tenant.rent_due_date - timezone.now().date()).days
        
        # Send reminder if within the reminder window
        if 0 <= days_until_due <= tenant.reminder_days_before:
            logger.info(f"Sending rent reminder to {tenant.full_name}")
            success, result = notification_service.send_rent_due_reminder(instance)
            
            if success:
                logger.info(f"Rent reminder sent successfully to {tenant.full_name}")
            else:
                logger.error(f"Failed to send rent reminder to {tenant.full_name}: {result}")


@receiver(post_save, sender=Payment)
def send_payment_confirmation(sender, instance, created, **kwargs):
    """
    Send payment confirmation SMS when payment is recorded
    """
    if created:
        logger.info(f"Sending payment confirmation to {instance.tenant.full_name}")
        success, result = notification_service.send_payment_confirmation(instance)
        
        if success:
            logger.info(f"Payment confirmation sent to {instance.tenant.full_name}")
        else:
            logger.error(f"Failed to send payment confirmation: {result}")


@receiver(post_save, sender=Tenant)
def send_welcome_message(sender, instance, created, **kwargs):
    """
    Send welcome message when new tenant is created and assigned to a house
    """
    if created and instance.house and instance.is_active:
        logger.info(f"Sending welcome message to {instance.full_name}")
        success, result = notification_service.send_move_in_welcome(instance)
        
        if success:
            logger.info(f"Welcome message sent to {instance.full_name}")
        else:
            logger.error(f"Failed to send welcome message: {result}")


@receiver(pre_save, sender=Tenant)
def notify_on_tenant_activation(sender, instance, **kwargs):
    """
    Send notification when tenant status changes
    """
    if instance.pk:
        try:
            old_instance = Tenant.objects.get(pk=instance.pk)
            
            # If tenant is being deactivated
            if old_instance.is_active and not instance.is_active:
                logger.info(f"Tenant {instance.full_name} deactivated")
                # You can send a move-out confirmation here if needed
                
            # If tenant is being reactivated
            elif not old_instance.is_active and instance.is_active:
                logger.info(f"Tenant {instance.full_name} reactivated")
                
        except Tenant.DoesNotExist:
            pass



@receiver(post_save, sender=User)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)



@receiver(post_delete, sender=Tenant)
def update_house_occupation(sender, instance, **kwargs):
    house_id = instance.house_id  # just get the raw ID (safe)
    if house_id and House.objects.filter(pk=house_id).exists():
        house = House.objects.get(pk=house_id)
        house.auto_change_occupation()


# whenever a Tenant is created or updated
@receiver(post_save, sender=Tenant)
def update_house_occupation_on_save(sender, instance, **kwargs):
    
    if instance.house:
        instance.house.auto_change_occupation()

# whenever a Payment is created if ghe amount field is blunk we getthe amount from the house rent
@receiver(pre_save, sender=Payment)
def set_payment_amount(sender, instance, **kwargs):
    if instance.amount is None or instance.amount == 0:
        if instance.tenant and instance.tenant.house:
            instance.amount = instance.tenant.house.house_rent_amount


@receiver(pre_delete, sender=Payment)
def adjust_tenant_balance_on_delete(sender, instance, **kwargs):
    tenant = instance.tenant
    if tenant:
        tenant.balance += instance.amount_paid


@receiver([post_save, post_delete], sender=Tenant)
def clear_tenant_cache(sender, instance, **kwargs):
    cache_key = f"tenant:{instance.id}"
    cache.delete(cache_key)



@receiver([post_save, post_delete], sender=House)
def clear_building_cache(sender, instance, **kwargs):
    if instance.flat_building_id:
        cache.delete(f"flat_{instance.flat_building_id}_occupied")
        cache.delete(f"flat_{instance.flat_building_id}_vacant")
        cache.delete(f"flat_{instance.flat_building_id}_tenant_count")