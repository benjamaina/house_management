from django.db import models, transaction
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from phonenumbers import parse, format_number, PhoneNumberFormat, NumberParseException
from django.core.exceptions import ValidationError
import logging
from django.core.cache import cache
from django.db.models import Sum

logger = logging.getLogger(__name__)



class FlatBuilding(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    building_name = models.CharField(max_length=50, blank=False, null=False)
    address = models.CharField(max_length=50)
    number_of_houses = models.IntegerField(default=0, db_index=True)

    @property
    def how_many_occupied(self):
        # culculate occupied houses
        return self.get_occupied_count()
    
    @property
    def vacant_houses(self):
        return self.get_vacant_count()

    def tenant_count(self):
        return self.houses.filter(tenants__is_active=True).distinct().count()

    
    def clean(self):
        if self.number_of_houses < 0:
            raise ValidationError("Number of houses must be non-negative")
        if not self.building_name:
            raise ValidationError("Building name is required")
 


    def delete(self, *args, **kwargs):
        if self.houses.filter(occupation=True).exists():
            raise ValidationError("Cannot delete a flat building with occupied houses.")
        super().delete(*args, **kwargs)



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
        self.full_clean()
   
        super().save()


    def __str__(self):
        return self.building_name




class Tenant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,blank=True, null=True)
    full_name = models.CharField(max_length=50, blank=False, null=False, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    phone = PhoneNumberField(unique=True, db_index= True)
    id_number = models.CharField(max_length=10,null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rent_due_date = models.DateField(default=datetime.now)
    house = models.ForeignKey('House', on_delete=models.CASCADE, related_name='tenants', blank=True, null=True, db_index=True)#house number
    is_active = models.BooleanField(default=True, db_index=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def building_name(self):
        if self.house and self.house.flat_building:
            return self.house.flat_building.building_name
        return None


    @property
    def building_adress(self):
        if self.house and self.house.flat_building:
            return self.house.flat_building.address
        return None


    @property
    def rent(self):
        if self.house:
            return self.house.house_rent_amount
        return 0
    
    @property
    def security_deposit(self):
        if self.house:
            return self.house.deposit_amount
        return 0

    def clean(self):
        if self.house and self.house.tenants.exclude(pk=self.pk).filter(is_active=True).exists():
            raise ValidationError(f"House {self.house} is already occupied by another tenant.")
    
        if self.balance < 0:
            raise ValidationError("Balance cannot be negative")
        if not self.full_name:
            raise ValidationError("Tenant full name is required")
        if not self.phone:
            raise ValidationError("Phone number is required")
        if self.id_number and Tenant.objects.exclude(pk=self.pk).filter(id_number=self.id_number).exists():
            raise ValidationError(f"ID number {self.id_number} is already in use")
        if self.house and not self.house.flat_building:
            raise ValidationError("House must be associated with a flat building")
        

    def update_balance(self):
        total_due = self.rent_payments.filter(is_paid=False).aggregate(
        total = Sum(models.F('rent_amount') - models.F('amount_paid'))
        )['total'] or 0
        self.balance = total_due
        # update only the balance field to avoid overwriting other changes
        self.save(update_fields=['balance'])
        return self.balance


    def save(self, *args, **kwargs):
        self.full_clean()
        logger.info(f"Saving tenant: {self.full_name}, Phone: {self.phone}, House: {self.house}, Active: {self.is_active}")
        super().save(*args, **kwargs)
   

    def __str__(self):
        return self.full_name





class House(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    flat_building = models.ForeignKey(FlatBuilding,related_name='houses',on_delete=models.CASCADE, db_index=True)
    house_number = models.CharField(max_length=5, db_index=True)
    house_size = models.CharField(max_length=10, default='1 bedroom')
    house_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, db_index=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,db_index=True)
    occupation = models.BooleanField(default=False)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['flat_building', 'house_number'], name='unique_house_per_building')
        ]


    def delete(self, *args, **kwargs):
        if self.occupation:
            raise ValidationError("cannot delete a house that is currently occupied ")

        super().delete(*args, **kwargs)


    def auto_change_occupation(self):
        new_house = self.tenants.filter(is_active=True).exists()
        if self.occupation != new_house:
            House.objects.filter(pk=self.pk).update(occupation=new_house)


    def clean(self):

        with transaction.atomic():
            existing_house = self.flat_building.houses.exclude(pk=self.pk).count()

            if not self.pk:
                existing_house += 1
                if existing_house > self.flat_building.number_of_houses:
                    raise ValidationError (
                    f"Cannot add house. {self.flat_building.building_name} "
                    f"can only have {self.flat_building.number_of_houses} houses "
                    f"(currently has {existing_house} houses)."
                )
                else:
                    if existing_house > self.flat_building.number_of_houses:
                        raise ValidationError (
                        f"Cannot add house. {self.flat_building.building_name} "
                        f"can only have {self.flat_building.number_of_houses} houses "
                        f"(currently has {existing_house} houses)."
                    )
            if self.flat_building.houses.filter(occupation=True).count() > self.flat_building.number_of_houses:
                raise ValidationError(f"Cannot occupy more houses than available in {self.flat_building.building_name}")
            if self.pk and self.occupation and self.tenants.filter(is_active=True).count() > 1:
                raise ValidationError(f"House {self.house_number} can only have one active tenant")
            if self.house_rent_amount < 0 or self.deposit_amount < 0:
                raise ValidationError("Rent amount and deposit must be non-negative")
            if not self.flat_building:
                raise ValidationError("House must be associated with a flat building")
            if not self.house_number:
                raise ValidationError("House number is required")
            if self.flat_building.houses.exclude(pk=self.pk).filter(house_number=self.house_number).exists():
                raise ValidationError(f"House number {self.house_number} already exists in {self.flat_building.building_name}")
            if self.flat_building.number_of_houses < self.flat_building.how_many_occupied:
                raise ValidationError(f"Number of houses in {self.flat_building.building_name} cannot be less than occupied houses")
            if self.flat_building.number_of_houses < 0:
                raise ValidationError("Number of houses must be non-negative")    
            

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    


    def __str__(self):
        return f"{self.flat_building.building_name} - House {self.house_number}"

    # def __str__(self):
    #     return f"House {self.house_number}"


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rent_payments', db_index=True)
    payment_date = models.DateField(auto_now_add=True)
    def current_year():
        return timezone.now().year
    year = models.IntegerField(default=current_year, db_index=True)
    rent_month = models.IntegerField(choices=MONTH_CHOICES)
    PAYNENT_METHODS = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),]
    payment_method = models.CharField(max_length=20, choices=PAYNENT_METHODS, default='cash')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=10, default=0, decimal_places=2)
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    class Meta:
        unique_together = ('tenant', 'rent_month', 'year')


    def fully_paid(self):
        return self.amount_paid >= self.rent_amount
    fully_paid.boolean = True

    @property
    def balance(self):
        return self.rent_amount - self.amount_paid
    
    def clean(self):
        if self.amount_paid < 0:
            raise ValidationError("amount paid cannot be negative")
        if self.rent_month < 1 or self.rent_month > 12:
            raise ValidationError("Rent month must be between 1 and 12")
        if not self.tenant:
            raise ValidationError("Rent payment must be associated with a tenant")
        if not self.tenant.house:
            raise ValidationError("Tenant must be assigned to a house to make a rent payment")
        


    def save(self, *args, **kwargs):
        self.full_clean()
        # auto get rent amount for a specific tenant from their house
        if not self.rent_amount and self.tenant and self.tenant.house:
            self.rent_amount = self.tenant.house.house_rent_amount
        super().save(*args, **kwargs)



    def update_payment_status(self):
        new_status = self.amount_paid >= ( self.rent_amount or 0)
        if self.is_paid != new_status:
            RentPayment.objects.filter(pk=self.pk).update(is_paid=new_status)
            self.refresh_from_db(fields=['is_paid'])

        return new_status

    def is_rent_due(self):
        today = timezone.now().date()
        return not self.is_paid and (self.year < today.year or (self.year == today.year and self.rent_month < today.month))


    def __str__(self):
        return f"RentPayment of {self.amount_paid} for {self.tenant.full_name} on {self.payment_date}"



class PaymentHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payment_history')
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name='payment_history')
    rent_payment = models.ForeignKey(RentPayment, on_delete=models.CASCADE, related_name='history')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(editable=False)
    payment_method = models.CharField(max_length=50) 
    
    def auto_set_fields(self):
        # set the fields automatically when a payment is made using 
        if self.rent_payment:
            try:
                if self.rent_payment:
                    self.tenant = self.tenant or self.rent_payment.tenant
                    self.house = self.house or self.rent_payment.tenant.house
                    self.payment_amount = self.payment_amount or self.rent_payment.amount_paid
                    self.payment_method = self.payment_method or self.rent_payment.payment_method
                    self.payment_date = self.payment_date or self.rent_payment.payment_date
            except Exception as e:
                logger.error(f"Error setting payment history fields: {e}")
                raise ValidationError("Error setting payment history fields.")
            
    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.pk:   
                self.auto_set_fields()
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.payment_amount} paid on {self.payment_date} via {self.payment_method}"
