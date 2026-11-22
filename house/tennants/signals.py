import logging

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.authtoken.models import Token

from tennants.services.sms import TwilioNotificationService
from .models import FlatBuilding, House, Payment, RentCharge, Tenant, HistoryReport

logger = logging.getLogger(__name__)

_service = None


def _invalidate_building_cache(building_id):
    """Invalidate cache for a building's occupied/vacant counts."""
    if building_id:
        cache.delete(f"flat_{building_id}_occupied")
        cache.delete(f"flat_{building_id}_vacant")


def _invalidate_tenant_cache(tenant_id):
    if tenant_id:
        cache.delete(f"tenant:{tenant_id}")


@receiver(post_save, sender=Payment)
def record_ledger_entry(sender, instance, created, **kwargs):
    if created:
        HistoryReport.record(instance)


@receiver(post_save, sender=House)
def invalidate_building_cache_on_house_save(sender, instance, **kwargs):
    _invalidate_building_cache(instance.flat_building_id)


@receiver(post_delete, sender=House)
def invalidate_building_cache_on_house_delete(sender, instance, **kwargs):
    _invalidate_building_cache(instance.flat_building_id)

def get_notification_service():
    """Created on first use, so a missing Twilio env var can't stop Django booting."""
    global _service
    if _service is None:
        _service = TwilioNotificationService()
    return _service


def _safe_send(label, func, obj):
    """SMS is best-effort: a failure must never roll back or crash the save."""
    try:
        success, result = func(obj)
        if success:
            logger.info("%s sent", label)
        else:
            logger.warning("%s not sent: %s", label, result)
    except Exception:
        logger.exception("%s failed", label)


def _send_after_commit(label, method_name, obj):
    transaction.on_commit(
        lambda: _safe_send(
            label, getattr(get_notification_service(), method_name), obj
        )
    )


@receiver(post_save, sender=RentCharge)
def send_rent_reminder_on_create(sender, instance, created, **kwargs):
    if not created or not instance.tenant.is_active:
        return
    tenant = instance.tenant
    if not tenant.sms_notifications or not tenant.phone:
        logger.info("Skipping rent reminder for tenant %s without SMS consent or phone", tenant.pk)
        return
    due = tenant.due_date_for(instance.year, instance.month)
    days_until_due = (due - timezone.localdate()).days
    if 0 <= days_until_due <= tenant.reminder_days_before:
        _send_after_commit(f"Rent reminder to {tenant.full_name}", "send_rent_due_reminder", instance)


@receiver(post_save, sender=Payment)
def send_payment_confirmation(sender, instance, created, **kwargs):
    tenant = instance.tenant
    if (created and not getattr(instance, "_skip_sms", False)
            and tenant.sms_notifications and tenant.phone):
        _send_after_commit(
            f"Payment confirmation to {tenant.full_name}",
            "send_payment_confirmation",
            instance,
        )


@receiver(post_save, sender=Tenant)
def send_welcome_message(sender, instance, created, **kwargs):
    if (created and instance.house_id and instance.is_active
            and instance.sms_notifications and instance.phone):
        _send_after_commit(f"Welcome message to {instance.full_name}", "send_move_in_welcome", instance)


# --- house occupancy -------------------------------------------------------

@receiver(pre_save, sender=Tenant)
def remember_previous_house(sender, instance, **kwargs):
    instance._old_house_id = None
    if instance.pk:
        instance._old_house_id = (
            Tenant.objects.filter(pk=instance.pk).values_list("house_id", flat=True).first()
        )

@receiver(post_save, sender=Tenant)
def update_house_occupation_on_save(sender, instance, **kwargs):
    _invalidate_tenant_cache(instance.pk)
    # recompute both the new house and the one the tenant just left
    ids = {instance.house_id, getattr(instance, "_old_house_id", None)} - {None}
    for house in House.objects.filter(pk__in=ids):
        house.auto_change_occupation()
        _invalidate_building_cache(house.flat_building_id)


@receiver(post_delete, sender=Tenant)
def update_house_occupation_on_delete(sender, instance, **kwargs):
    _invalidate_tenant_cache(instance.pk)
    if instance.house_id:
        for house in House.objects.filter(pk=instance.house_id):
            house.auto_change_occupation()
            _invalidate_building_cache(house.flat_building_id)


# --- auth ------------------------------------------------------------------

@receiver(post_save, sender=User)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.get_or_create(user=instance)