from django.conf import settings
from django.db.models.signals import post_save,post_delete,pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import RentPayment, House
from django.core.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from .models import Tennant, FlatBuilding, House

@receiver(post_save, sender=User)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)
@receiver(post_delete, sender = Tennant)
def update_house_occupation(sender, instance, **kwargs):
    if instance.house:
        instance.house.auto_change_occupation()

@receiver(post_save, sender=House)
@receiver(post_delete, sender=House)

def update_flat_building_on_house_change(sender, instance, **kwargs):
    flat_building = instance.flat_building
    flat_building.save()  # Recalculates and updates the occupied and vacant house counts

