from django.db import models, transaction
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)

# ------------------------------
# FlatBuilding Model
# ------------------------------
class FlatBuilding(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    building_name = models.CharField(max_length=50)
    address = models.CharField(max_length=50)
    number_of_houses = models.IntegerField(default=0, db_index=True)

    @property
    def how_many_occupied(self):
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
        occupied = self.houses.filter(occupation=True).count()
        return occupied

    def get_vacant_count(self):
        return self.number_of_houses - self.get_occupied_count()

    def clean(self):
        if self.number_of_houses < 0:
            raise ValidationError("Number of houses must be non-negative")
        if not self.building_name:
            raise ValidationError("Building name is required")

    def __str__(self):
        return self.building_name


# ------------------------------
# House Model
# ------------------------------
class House(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    flat_building = models.ForeignKey(FlatBuilding, related_name='houses', on_delete=models.CASCADE, db_index=True)
    house_number = models.CharField(max_length=5, db_index=True)
    house_size = models.CharField(max_length=10, default='1 bedroom')
    house_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, db_index=True)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, db_index=True)
    occupation = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['flat_building', 'house_number'], name='unique_house_per_building')
        ]
    
    def auto_change_occupation(self):   
        is_occupied = self.tenants.filter(is_active=True).exists()
        if self.occupation != is_occupied:
            self.occupation = is_occupied
            self.save()

    def clean(self):
        if not self.flat_building_id:
            raise ValidationError("House must be associated with a flat building")
        if self.house_rent_amount < 0 or self.deposit_amount < 0:
            raise ValidationError("Rent and deposit must be non-negative")
        if self.flat_building.houses.exclude(pk=self.pk).filter(house_number=self.house_number).exists():
            raise ValidationError(f"House number {self.house_number} already exists in {self.flat_building.building_name}")
        # ensure number of houses in building is not exceeded
        if self._state.adding:  # only on create
            current_house_count = self.flat_building.houses.count()
            if current_house_count >= self.flat_building.number_of_houses:
                raise ValidationError(f"Cannot add more houses to {self.flat_building.building_name}. Limit reached.")
        

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.flat_building.building_name} - House {self.house_number}"


# ------------------------------
# Tenant Model
# ------------------------------
class Tenant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    full_name = models.CharField(max_length=50, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    phone = PhoneNumberField(unique=True, db_index=True)
    id_number = models.CharField(max_length=10, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rent_due_date = models.DateField(default=datetime.now)
    house = models.ForeignKey(House, on_delete=models.CASCADE, related_name='tenants', blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    @property
    def building_name(self):
        return self.house.flat_building.building_name if self.house and self.house.flat_building else None

    @property
    def building_address(self):
        return self.house.flat_building.address if self.house and self.house.flat_building else None

    @property
    def rent(self):
        return self.house.house_rent_amount if self.house else 0

    @property
    def security_deposit(self):
        return self.house.deposit_amount if self.house else 0

    @property
    def balance(self):
        total_due = self.rent_charges.aggregate(total=Sum('amount_due'))['total'] or 0
        total_paid = self.payments.aggregate(total=Sum('amount'))['total'] or 0
        return total_due - total_paid

    def clean(self):
        if self.house and self.house.tenants.exclude(pk=self.pk).filter(is_active=True).exists():
            raise ValidationError(f"House {self.house} is already occupied by another tenant.")
        if not self.full_name:
            raise ValidationError("Tenant full name is required")
        if not self.phone:
            raise ValidationError("Phone number is required")
        if self.id_number and Tenant.objects.exclude(pk=self.pk).filter(id_number=self.id_number).exists():
            raise ValidationError(f"ID number {self.id_number} is already in use")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name

# ------------------------------
# RentCharge Model (Obligation)
# ------------------------------
class RentCharge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="rent_charges")
    year = models.IntegerField()
    month = models.IntegerField(choices=MONTH_CHOICES)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ("tenant", "year", "month")

    def save(self, *args, **kwargs):
        # auto-set amount_due from tenant's house
        if self.amount_due is None and self.tenant and self.tenant.house:
            self.amount_due = self.tenant.house.house_rent_amount
        super().save(*args, **kwargs)

    @property
    def total_paid(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or 0

    @property
    def balance(self):
        return self.amount_due - self.total_paid

    @property
    def is_paid(self):
        return self.balance <= 0

    def __str__(self):
        return f"{self.tenant.full_name} - {self.get_month_display()} {self.year}"


# ------------------------------
# Payment Model (Ledger)
# ------------------------------
class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    rent_charge = models.ForeignKey(RentCharge, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_reference = models.TextField(blank=True, null=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.payment_method != "cash" and not self.payment_reference:
            raise ValidationError({
                "payment_reference": "Reference required for non-cash payments"
            })
        
        if self.rent_charge and self.tenant != self.rent_charge.tenant:
            raise ValidationError("Payment tenant must match rent charge tenant")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} paid by {self.tenant.full_name} via {self.payment_method} on {self.paid_at.date()}"