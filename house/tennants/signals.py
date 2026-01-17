from django.conf import settings
from django.db.models.signals import post_save,post_delete,pre_delete
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


@receiver(post_save, sender=Payment)
def set_payment_status_on_save(sender, instance, **kwargs):
    # automatically recalc is_paid on save
    rent_amount = instance.amount or 0
    instance.is_paid = instance.amount >= rent_amount
    # prevent recursive save signals
    instance.save(update_fields=['is_paid'])

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