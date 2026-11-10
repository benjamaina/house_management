from django.db import models, transaction
from django.contrib.auth.models import User
from datetime import datetime
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.db.models import Sum
import logging
import calendar
from datetime import timedelta, date
import secrets


logger = logging.getLogger(__name__)

# ------------------------------
# FlatBuilding Model
# ------------------------------
class FlatBuilding(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)
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
        if self.pk:
            existing = self.houses.count()
            if self.number_of_houses < existing:
                raise ValidationError(
                    f"Capacity cannot be lower than the {existing} houses already in this building."
                )

            
    def delete(self, *args, **kwargs):
        if self.houses.filter(occupation=True).exists():
            raise ValidationError("Cannot delete a flat building with occupied houses.")
        super().delete(*args, **kwargs)

    def get_occupied_count(self):
        occupied = self.houses.filter(occupation=True).count()
        return occupied

    def get_vacant_count(self):
        return self.number_of_houses - self.get_occupied_count()

    def __str__(self):
        return self.building_name


# ------------------------------
# House Model
# ------------------------------
class House(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_index=True)
    flat_building = models.ForeignKey(FlatBuilding, related_name='houses', on_delete=models.PROTECT, db_index=True)
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
            House.objects.filter(pk=self.pk).update(occupation=is_occupied)
            self.occupation = is_occupied

    def clean(self):
        if not self.flat_building_id:
            raise ValidationError("House must be associated with a flat building")
        if self.house_rent_amount <= 0 or self.deposit_amount < 0:
            raise ValidationError("Rent and deposit must be non-negative")
        if self.flat_building.houses.exclude(pk=self.pk).filter(house_number=self.house_number).exists():
            raise ValidationError(f"House number {self.house_number} already exists in {self.flat_building.building_name}")
        # ensure number of houses in building is not exceeded
        if self._state.adding:  # only on create
            current_house_count = self.flat_building.houses.count()
            if current_house_count >= self.flat_building.number_of_houses:
                raise ValidationError(f"Cannot add more houses to {self.flat_building.building_name}. Limit reached.")
        # ensure we cant edit the rent amount if there are active tenants
        if not self._state.adding and self.house_rent_amount != self.__class__.objects.get(pk=self.pk).house_rent_amount:
            if self.tenants.filter(is_active=True).exists():
                raise ValidationError("Cannot change rent amount while there are active tenants.")
        

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.flat_building.building_name} - House {self.house_number}"


# ------------------------------
# Tenant Model
# ------------------------------
class Tenant(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_index=True)
    full_name = models.CharField(max_length=50, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    phone = PhoneNumberField(unique=True, db_index=True)
    id_number = models.CharField(max_length=10, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rent_due_date = models.DateField(default=timezone.localdate)
    house = models.ForeignKey(House, on_delete=models.PROTECT, related_name='tenants', blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sms_notifications = models.BooleanField(default=True, db_index=True)
    last_notification_sent = models.DateTimeField(blank=True, null=True)
    reminder_days_before = models.IntegerField(default=3, db_index=True)
    last_reminder_sent = models.DateTimeField(blank=True, null=True)
    

    def due_date_for(self, year, month):
        """Due date of the charge for a given month, clamped to the month's length."""
        day = min(
    self.rent_due_date.day,
    calendar.monthrange(year, month)[1]
)
        return date(year, month, day)


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
        if self.is_active and self.house_id and \
                self.house.tenants.exclude(pk=self.pk).filter(is_active=True).exists():
            raise ValidationError(f"House {self.house} is already occupied by another tenant.")
        if not self.full_name:
            raise ValidationError("Tenant full name is required")
        if not self.phone:
            raise ValidationError("Phone number is required")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.house_id:
                # row lock: serialises concurrent assignments to the same house
                House.objects.select_for_update().filter(pk=self.house_id).first()
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name

# ------------------------------
# RentCharge Model (Obligation)
# ------------------------------
class RentCharge(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_index=True)
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="rent_charges", db_index=True)
    year = models.IntegerField()
    month = models.IntegerField(choices=MONTH_CHOICES)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(blank=True, null=True)


    class Meta:
        unique_together = ("tenant", "year", "month")

    def clean(self):
        if self.year is not None and not (2000 <= self.year <= 2100):
            raise ValidationError({"year": "Enter a valid year."})
        if self.amount_due is not None and self.amount_due < 0:
            raise ValidationError({"amount_due": "Amount due cannot be negative."})
        # check if a charge for this tenant, year, and month already exists
        if self.tenant_id and self.year and self.month:
            existing = RentCharge.objects.filter(
                tenant_id=self.tenant_id, year=self.year, month=self.month
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    f"A charge for {self.get_month_display()} {self.year} already exists for this tenant."
                )
        # ensure amount_due matches the tenant's house rent if the tenant has a house
        if self.tenant_id and self.tenant.house_id:
            expected_amount = self.tenant.house.house_rent_amount
            if self.amount_due != expected_amount:
                raise ValidationError(
                    {"amount_due": f"Amount due must match the tenant's house rent ({expected_amount})."}
                )
        # ensure when creating a rent charge, we dont  create a charge behind the last charge for this tenant
        if self._state.adding and self.tenant_id:
            last_charge = RentCharge.objects.filter(tenant_id=self.tenant_id).order_by('-year', '-month').first()
            if last_charge:
                if (self.year, self.month) <= (last_charge.year, last_charge.month):
                    raise ValidationError(
                        f"Cannot create a charge for {self.get_month_display()} {self.year} "
                        f"because a later charge already exists for this tenant."
                    )


    def save(self, *args, **kwargs):
        if self.tenant_id:
            if self.amount_due is None and self.tenant.house_id:
                self.amount_due = self.tenant.house.house_rent_amount
            if not self.user_id:
                self.user_id = self.tenant.user_id   # charges can no longer be orphaned
        self.full_clean()
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

class LedgerImmutableError(ValidationError):
    """Subclasses ValidationError so the ApiViewMixin from earlier turns it into a 400."""


class AppendOnlyQuerySet(models.QuerySet):
    def delete(self):
        raise LedgerImmutableError("Ledger records cannot be deleted.")

    def update(self, **kwargs):
        raise LedgerImmutableError("Ledger records cannot be modified.")

    def bulk_update(self, *args, **kwargs):
        raise LedgerImmutableError("Ledger records cannot be modified.")

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_index=True)
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="payments")
    rent_charge = models.ForeignKey(RentCharge, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_reference = models.TextField(blank=True, null=True)
    bank_transaction = models.ForeignKey(
        "BankTransaction", null=True, blank=True,
        on_delete=models.PROTECT, related_name="payments",
    )
    paid_at = models.DateTimeField(default=timezone.now, db_index=True)
    objects = AppendOnlyQuerySet.as_manager()
    _LOCKED_FIELDS = ['tenant_id', 'rent_charge_id', 'amount', 'payment_method', 'payment_reference', 'paid_at']


    def clean(self):
        super().clean()
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})
        if self.payment_method != "cash" and not self.payment_reference:
            raise ValidationError({"payment_reference": "Reference required for non-cash payments"})
        if self.rent_charge_id and self.tenant_id and self.tenant_id != self.rent_charge.tenant_id:
            raise ValidationError("Payment tenant must match rent charge tenant")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self._state.adding:
                original = type(self).objects.filter(pk=self.pk).values(*self._LOCKED_FIELDS).first()
                current = {f: getattr(self, f) for f in self._LOCKED_FIELDS}
                if original != current:
                    raise LedgerImmutableError(
                        "Payments cannot be edited. Record a correcting entry instead.")
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("Payments cannot be deleted. Record a correcting entry instead.")

    def __str__(self):
        return f"{self.amount} paid by {self.tenant.full_name} via {self.payment_method} on {self.paid_at.date()}"


# =================================================================
#PAYMENTS REPORTS
# =================================================================
class HistoryReport(models.Model):
    objects = AppendOnlyQuerySet.as_manager()

    user = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="history_reports", db_index=True)
    rent_charge = models.ForeignKey(RentCharge, on_delete=models.PROTECT, related_name="history_reports", db_index=True)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="history_reports", db_index=True)

    # --- snapshot: what was true at the moment of payment ---
    tenant_name = models.CharField(max_length=50)
    tenant_phone = models.CharField(max_length=20, blank=True)
    tenant_id_number = models.CharField(max_length=10, blank=True)
    building_name = models.CharField(max_length=50, blank=True)
    house_number = models.CharField(max_length=5, blank=True)
    charge_year = models.PositiveSmallIntegerField()
    charge_month = models.PositiveSmallIntegerField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20)
    payment_reference = models.TextField(blank=True)
    paid_at = models.DateTimeField()
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)  # charge balance after this payment

    report_generated_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def record(cls, payment):
        tenant, charge = payment.tenant, payment.rent_charge
        house = tenant.house
        return cls.objects.create(
            user_id=payment.user_id, tenant=tenant, rent_charge=charge, payment=payment,
            tenant_name=tenant.full_name,
            tenant_phone=str(tenant.phone),
            tenant_id_number=tenant.id_number or "",
            building_name=house.flat_building.building_name if house else "",
            house_number=house.house_number if house else "",
            charge_year=charge.year, charge_month=charge.month,
            amount_due=charge.amount_due,
            amount_paid=payment.amount,
            payment_method=payment.payment_method,
            payment_reference=payment.payment_reference or "",
            paid_at=payment.paid_at,
            balance_after=charge.balance,
        )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError("Ledger entries cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("Ledger entries cannot be deleted.")

    def __str__(self):
        return f"{self.tenant_name} - {self.amount_paid} on {self.paid_at.date()}"


# =================================================================
# BANK STATEMENT RECONCILIATION
# =================================================================
def _new_inbound_token():
    return secrets.token_hex(8)


class LandlordProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="landlord_profile")
    phone = PhoneNumberField(blank=True, null=True)          # where the summary SMS goes
    notify_sms = models.BooleanField(default=True)
    inbound_token = models.CharField(max_length=32, unique=True, default=_new_inbound_token)
    auto_approve_email = models.BooleanField(default=False)  # trust forwarded emails?

    def __str__(self):
        return f"Profile for {self.user.username}"


class StatementUpload(models.Model):
    SOURCES = [("equity", "Equity Bank"), ("kcb", "KCB"), ("coop", "Co-operative Bank"),
               ("mpesa", "M-Pesa"), ("generic", "Other bank")]
    STATUSES = [("pending", "Pending"), ("processing", "Processing"),
                ("done", "Done"), ("failed", "Failed")]
    CHANNELS = [("upload", "Uploaded"), ("email", "Forwarded email")]

    user = models.ForeignKey(User, on_delete=models.PROTECT)
    file = models.FileField(upload_to="statements/%Y/%m/")
    original_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    source = models.CharField(max_length=10, choices=SOURCES, default="generic")
    channel = models.CharField(max_length=10, choices=CHANNELS, default="upload")
    status = models.CharField(max_length=12, choices=STATUSES, default="pending", db_index=True)
    error = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    auto_matched = models.PositiveIntegerField(default=0)
    needs_review = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-uploaded_at"]
        constraints = [models.UniqueConstraint(fields=["user", "file_hash"], name="uniq_statement_per_user")]

    def __str__(self):
        return f"{self.original_name} ({self.get_status_display()})"


class BankTransaction(models.Model):
    STATUSES = [("auto", "Auto-matched"), ("review", "Needs review"),
                ("manual", "Assigned manually"), ("ignored", "Ignored")]

    user = models.ForeignKey(User, on_delete=models.PROTECT)
    upload = models.ForeignKey(StatementUpload, on_delete=models.PROTECT, related_name="transactions")
    txn_date = models.DateField(db_index=True)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=60, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    dedupe_key = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=STATUSES, default="review", db_index=True)
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.PROTECT,
                               related_name="bank_transactions")
    suggested_tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="+")
    confidence = models.PositiveSmallIntegerField(default=0)
    match_reason = models.CharField(max_length=200, blank=True)
    review_note = models.CharField(max_length=200, blank=True)   # why it was NOT auto-approved
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-txn_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "dedupe_key"], name="uniq_bank_txn_per_user")]

    def __str__(self):
        return f"KES {self.amount} on {self.txn_date} ({self.get_status_display()})"


class PaymentAlias(models.Model):
    """Payer text the landlord has confirmed belongs to a tenant ('KAMAU JOHN' -> tenant)."""
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="aliases")
    alias = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "alias"], name="uniq_alias_per_user")]