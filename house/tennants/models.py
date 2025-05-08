from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from phonenumbers import parse, format_number, PhoneNumberFormat, NumberParseException
from django.core.exceptions import ValidationError
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)
# Create your models here.
class Tennant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    phone = PhoneNumberField(unique=True, db_index= True)
    id_number = models.CharField(max_length=10,null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rent_due_date = models.DateField(default=datetime.now)
    house = models.ForeignKey('House', on_delete=models.CASCADE, related_name='tennants', blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
     


    def clean(self):
        if self.house.tennants.exclude(pk=self.pk).filter(is_active=True).exists():
            raise ValidationError(f"House {self.house} is already occupied by another tenant.")
               
    def outstanding_rent(self):
        unpaid_rent = self.rent_payments.filter(is_paid=False)
        if unpaid_rent.exists():
            total = unpaid_rent.aggregate(models.Sum('amount'))['amount__sum']
            return total or 0
        return 0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.house:
            self.house.auto_change_occupation()

    def __str__(self):
        return self.name

class FlatBuilding(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flat_buildings', blank=True, null=True)
    name = models.CharField(max_length=50, blank=False, null=False)
    address = models.CharField(max_length=50)
    number_of_houses = models.IntegerField(default=0)
    how_many_occupied = models.IntegerField(default=0, editable=False)
    vacant_houses = models.IntegerField(default=0, editable=False)

    
    def delete(self, *args, **kwargs):
        if self.houses.filter(occupation=True).exists():
            raise ValidationError("Cannot delete a flat building with occupied houses.")
        super().delete(*args, **kwargs)

    def update_house_counts(self):
        logger.info("Updating house counts")
        occupied_count = self.houses.filter(occupation = True).count()
        vacant_count = self.number_of_houses - occupied_count

        self.how_many_occupied = occupied_count
        self.vacant_houses = vacant_count

        cache.set(f"flat_{self.pk}_occupied", occupied_count,  timeout = 600*15,)
        cache.set(f"flat_{self.pk}_vacant", vacant_count, timeout=600*15)

        self.save(update_fields = ['how_many_occupied', 'vacant_houses'])


    def get_occupied_count(self):
            """ Retrieve occupied houses from cache or database. """
            occupied = cache.get(f"flat_{self.pk}_occupied")

            if occupied is None:
                occupied = self.houses.filter(occupation=True).count()
                cache.set(f"flat_{self.pk}_occupied", occupied, timeout=60*15)

            return occupied

    def get_vacant_count(self):
        vacant = cache.get(f"flat_{self.pk}_vacant")

        if vacant is None:
            vacant = self.number_of_houses - self.get_occupied_count()
            cache.set(f"flat_{self.pk}_vacant", vacant, timeout=60*15)

        return vacant

    def save(self, *args, **kwargs):
        self.clean()
        logger.info("saving Flatbiulding")
        print('saving the flat')

        is_new = self.pk is None
        super().save(*args, **kwargs)

        logger.info(f'Flatbiulding saved with pk={self.pk}')
        print(f"flat biulding saved")    

        if not is_new:
            self.how_many_occupied = self.houses.filter(occupation=True).count()    
            self.vacant_houses = self.number_of_houses - self.how_many_occupied
            
            super().save(update_fields=['how_many_occupied', 'vacant_houses'])


    def __str__(self):
        return self.name

class House(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='houses', blank=True, null=True)
    flat_building = models.ForeignKey(FlatBuilding,related_name='houses',on_delete=models.CASCADE)
    house_num = models.CharField(max_length=5, unique=True)
    house_size = models.CharField(max_length=10, default='1 bedroom')
    house_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    occupation = models.BooleanField(default=False)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['flat_building', 'house_num'], name='unique_house_per_building')
        ]


    def delete(self, *args, **kwargs):
        if self.occupation:
            raise ValidationError("cannot delete a house that is currently occupied ")

        super().delete(*args, **kwargs)


    def auto_change_occupation(self):
        self.occupation = self.tennants.filter(is_active=True).exists()
        self.save(update_fields=['occupation'])

        # Update the flat building house counts only if flat_building still exists
        if FlatBuilding.objects.filter(pk=self.flat_building_id).exists():
            self.flat_building.update_house_counts()


    def one_tennant(self):
        if self.tennants.count() > 1:
            raise ValidationError(f"House {self.house_num} can only have one tennant")
        return True

    def clean(self):
        if not self.pk:
            if self.flat_building.number_of_houses > 0:
                number_of_houses = House.objects.filter(flat_building=self.flat_building).count()
                if number_of_houses  >= self.flat_building.number_of_houses:
                    raise ValidationError(f'The building {self.flat_building.name} is full')
        

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        self.flat_building.save(update_fields=['how_many_occupied', 'vacant_houses'])


    def tennant_count(self):
        return f"house{self.house_num}- {self.flat_building.name} has {self.tennants.count()} tennants"


    def __str__(self):
        return f"House {self.house_num}"


class RentPayment(models.Model):
    MONTH_CHOICES = [
        (1, 'January'),
        (2, 'February'),
        (3, 'March'),
        (4, 'April'),
        (5, 'May'),
        (6, 'June'),
        (7, 'July'),
        (8, 'August'),
        (9, 'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rent_payments', blank=True, null=True)
    tennant = models.ForeignKey(Tennant, on_delete=models.CASCADE, related_name='rent_payments')
    payment_date = models.DateField(auto_now_add=True)
    rent_month = models.IntegerField(choices=MONTH_CHOICES)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    partial_amount_paid = models.DecimalField(max_digits=10, default=0, decimal_places=2)
    confermation_recieved = models.BooleanField(default=False)
    grace_period = models.IntegerField(default=5)

    @property
    def amount(self):
        return self.tennant.house.house_rent_amount

        
    @property
    def balance(self):
        return self.amount - self.partial_amount_paid
    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.amount:
                if self.tennant and self.tennant.house:
                    self.amount = self.tennant.house.house_rent_amount
                     
                else:
                    raise ValidationError('House rent amount not set')
            super().save(*args, **kwargs)


    def grace_rent_period(self):
        if not self.is_paid and (self.payment_date - self.tennant.rent_due_date).days <= self.grace_period:
            return True
        return False


    def update_payment_status(self):
        if self.partial_amount_paid >= self.amount:
            self.is_paid = True
        else:
            self.is_paid = False
        self.save(update_fields=['is_paid'])

    def is_rent_due(self):
        current_month = timezone.now().month
        return not self.is_paid and self.rent_month < current_month

    def calculate_late_fee(self):
        if not self.is_paid and self.payment_date > self.rent_due_date:
            days_late = (self.payment_date - self.tennant.rent_due_date).days
            late_fee = self.amount * 0.05 * days_late  
            return late_fee
        return 0

    def send_payment_reminder(self):
        if self.is_paid:
            return
        if timezone.now().date() >= self.rent_due_date:
            # Logic to send email/SMS reminder to the tenant
            pass


    def __str__(self):
        return f'paymen of {self.amount} by {self.tennant.name}'



class PaymentHistory(models.Model):
    rent_payment = models.ForeignKey(RentPayment, on_delete=models.CASCADE, related_name='history')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=50) 
    
    def __str__(self):
        return f"{self.payment_amount} paid on {self.payment_date} via {self.payment_method}"
