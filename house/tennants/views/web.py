"""
Server-rendered (HTML) views for the tennants app.

Conventions used throughout this module:
  * Every queryset is scoped to request.user (multi-landlord isolation).
  * Model-level ValidationError / ProtectedError are turned into friendly
    messages instead of 500 pages.
  * Payments are ledger entries: they can be created, never edited or deleted.
"""
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, ProtectedError, Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tennants.forms import RentChargeForm
from tennants.models import FlatBuilding, House, Payment, RentCharge, Tenant
from tennants.serializers import ForgotPasswordSerializer
from tennants.services import reconcile as engine
from tennants.services.sms import TwilioNotificationService, reminder_candidates

logger = logging.getLogger(__name__)


# ============================================================================
# SHARED MIXINS
# ============================================================================

class OwnedQuerysetMixin:
    """Restrict a view's queryset to the logged-in landlord's own records."""

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class FormSaveMixin:
    """
    Create/Update views: show a success message only AFTER the save succeeds, and
    turn model-level validation errors raised during save() (e.g. a race on
    house occupancy) into normal form errors instead of a 500.
    """
    success_message = ""

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except DjangoValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response


class ProtectedDeleteMixin:
    """
    Delete views: records with financial history are PROTECTed at the database
    level. Show a friendly message instead of a ProtectedError 500.
    """
    success_message = "Deleted successfully."
    protected_message = (
        "This record has financial history and can't be deleted. "
        "Mark it inactive instead."
    )

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except (ProtectedError, DjangoValidationError):
            messages.error(self.request, self.protected_message)
            return redirect(self.get_success_url())
        messages.success(self.request, self.success_message)
        return response


# ============================================================================
# PUBLIC / ACCOUNT
# ============================================================================

def landing_page(request):
    """Render the landing page."""
    return render(request, "landing.html")


class ForgotPasswordViewWeb(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Same response whether or not the account exists (no user enumeration)
        return Response({"message": "If the account exists, reset instructions were sent."})


# ============================================================================
# DASHBOARD
# ============================================================================

def _buildings_with_counts(user):
    """Buildings with occupied/vacant counts computed in ONE query (no N+1)."""
    return (
        FlatBuilding.objects.filter(user=user)
        .annotate(occupied_count=Count("houses", filter=Q(houses__occupation=True)))
        .annotate(vacant_count=F("number_of_houses") - F("occupied_count"))
        .order_by("building_name")
    )


@login_required
def dashboard(request):
    """Main dashboard showing summary stats."""
    stats = House.objects.filter(user=request.user).aggregate(
        total=Count("id"),
        occupied=Count("id", filter=Q(occupation=True)),
    )
    total_houses = stats["total"]
    occupied_houses = stats["occupied"]
    active_tenants = Tenant.objects.filter(user=request.user, is_active=True).count()

    recent_payments = (
        Payment.objects.filter(user=request.user)
        .select_related("tenant", "rent_charge")
        .order_by("-paid_at")[:5]
    )

    percent_occupied = round((occupied_houses / total_houses) * 100, 2) if total_houses else 0.0

    context = {
        "buildings": _buildings_with_counts(request.user),
        "total_houses": total_houses,
        "occupied_houses": occupied_houses,
        "vacant_houses": total_houses - occupied_houses,
        "active_tenants": active_tenants,
        "recent_payments": recent_payments,
        "percent_occupied": percent_occupied,
    }
    return render(request, "dashboard.html", context)


# ============================================================================
# BUILDINGS
# ============================================================================

class BuildingListViewWeb(LoginRequiredMixin, ListView):
    model = FlatBuilding
    template_name = "buildings/building_list.html"
    context_object_name = "buildings"

    def get_queryset(self):
        return _buildings_with_counts(self.request.user)


class BuildingCreateViewWeb(LoginRequiredMixin, FormSaveMixin, CreateView):
    model = FlatBuilding
    fields = ["building_name", "address", "number_of_houses"]
    template_name = "buildings/building_form.html"
    success_url = reverse_lazy("building_list")
    success_message = "Building created successfully!"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class BuildingUpdateViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, FormSaveMixin, UpdateView):
    model = FlatBuilding
    fields = ["building_name", "address", "number_of_houses"]
    template_name = "buildings/building_form.html"
    success_url = reverse_lazy("building_list")
    success_message = "Building updated successfully!"


class BuildingDeleteViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, ProtectedDeleteMixin, DeleteView):
    model = FlatBuilding
    template_name = "buildings/building_confirm_delete.html"
    success_url = reverse_lazy("building_list")
    success_message = "Building deleted successfully!"
    protected_message = (
        "This building can't be deleted because its houses have tenants or "
        "financial records attached."
    )

    def form_valid(self, form):
        # NOTE: delete() is not called for POSTs in Django 4+, so the check lives here
        if self.object.houses.filter(occupation=True).exists():
            messages.error(self.request, "Cannot delete a building with occupied houses!")
            return redirect("building_list")
        return super().form_valid(form)


class BuildingDetailViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, DetailView):
    model = FlatBuilding
    template_name = "buildings/building_detail.html"
    context_object_name = "building"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["houses"] = self.object.houses.order_by("house_number")
        return context


# ============================================================================
# HOUSES
# ============================================================================

class HouseListViewWeb(LoginRequiredMixin, ListView):
    model = House
    template_name = "houses/house_list.html"
    context_object_name = "houses"

    def get_queryset(self):
        queryset = House.objects.filter(user=self.request.user).select_related("flat_building")
        building_id = self.request.GET.get("building")
        if building_id:
            queryset = queryset.filter(flat_building_id=building_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["buildings"] = FlatBuilding.objects.filter(user=self.request.user)
        return context


class HouseCreateViewWeb(LoginRequiredMixin, FormSaveMixin, CreateView):
    model = House
    fields = ["flat_building", "house_number", "house_size", "house_rent_amount", "deposit_amount"]
    template_name = "houses/house_form.html"
    success_url = reverse_lazy("house_list")
    success_message = "House created successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["flat_building"].queryset = FlatBuilding.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class HouseUpdateViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, FormSaveMixin, UpdateView):
    model = House
    fields = ["flat_building", "house_number", "house_size", "house_rent_amount", "deposit_amount"]
    template_name = "houses/house_form.html"
    success_url = reverse_lazy("house_list")
    success_message = "House updated successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["flat_building"].queryset = FlatBuilding.objects.filter(user=self.request.user)
        return form


class HouseDeleteViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, ProtectedDeleteMixin, DeleteView):
    model = House
    template_name = "houses/house_confirm_delete.html"
    success_url = reverse_lazy("house_list")
    success_message = "House deleted successfully!"
    protected_message = "This house has tenants or financial records and can't be deleted."


class HouseDetailViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, DetailView):
    model = House
    template_name = "houses/house_detail.html"
    context_object_name = "house"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenant"] = self.object.tenants.filter(is_active=True).first()
        return context


# ============================================================================
# TENANTS
# ============================================================================

class TenantListViewWeb(LoginRequiredMixin, ListView):
    model = Tenant
    template_name = "tenants/tenant_list.html"
    context_object_name = "tenants"

    def get_queryset(self):
        queryset = Tenant.objects.filter(user=self.request.user).select_related("house__flat_building")
        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        return queryset


class TenantCreateViewWeb(LoginRequiredMixin, FormSaveMixin, CreateView):
    model = Tenant
    fields = ["full_name", "email", "phone", "id_number", "house", "rent_due_date"]
    template_name = "tenants/tenant_form.html"
    success_url = reverse_lazy("tenant_list")
    success_message = "Tenant added successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # only the landlord's own vacant houses
        form.fields["house"].queryset = House.objects.filter(
            user=self.request.user, occupation=False
        ).select_related("flat_building")
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class TenantUpdateViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, FormSaveMixin, UpdateView):
    model = Tenant
    fields = ["full_name", "email", "phone", "id_number", "house", "rent_due_date", "is_active"]
    template_name = "tenants/tenant_form.html"
    success_url = reverse_lazy("tenant_list")
    success_message = "Tenant updated successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["house"].queryset = House.objects.filter(
            user=self.request.user
        ).select_related("flat_building")
        return form


class TenantDeleteViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, ProtectedDeleteMixin, DeleteView):
    model = Tenant
    template_name = "tenants/tenant_confirm_delete.html"
    success_url = reverse_lazy("tenant_list")
    success_message = "Tenant deleted successfully!"
    protected_message = (
        "This tenant has rent charges or payments and can't be deleted. "
        "Mark the tenant as inactive instead."
    )


class TenantDetailViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, DetailView):
    model = Tenant
    template_name = "tenants/tenant_detail.html"
    context_object_name = "tenant"

    def get_queryset(self):
        return super().get_queryset().select_related("house__flat_building")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payments"] = (
            self.object.payments.select_related("rent_charge").order_by("-paid_at")
        )
        context["rent_charges"] = self.object.rent_charges.order_by("-year", "-month")
        return context


# ============================================================================
# PAYMENTS (ledger: create + read only)
# ============================================================================

class PaymentListViewWeb(LoginRequiredMixin, ListView):
    model = Payment
    template_name = "payments/payment_list.html"
    context_object_name = "payments"

    def get_queryset(self):
        queryset = Payment.objects.filter(user=self.request.user).select_related("tenant", "rent_charge")
        tenant_id = self.request.GET.get("tenant")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by("-paid_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenants"] = Tenant.objects.filter(user=self.request.user)
        return context


class PaymentDetailViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, DetailView):
    model = Payment
    template_name = "payments/payment_detail.html"
    context_object_name = "payment"

    def get_queryset(self):
        return super().get_queryset().select_related("tenant", "rent_charge")


class PaymentCreateViewWeb(LoginRequiredMixin, FormSaveMixin, CreateView):
    model = Payment
    fields = ["tenant", "rent_charge", "amount", "payment_reference", "payment_method"]
    template_name = "payments/payment_form.html"
    success_url = reverse_lazy("payment_list")
    success_message = "Payment recorded successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["tenant"].queryset = Tenant.objects.filter(user=self.request.user)
        # previously listed EVERY landlord's charges
        form.fields["rent_charge"].queryset = RentCharge.objects.filter(
            user=self.request.user
        ).select_related("tenant")
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class PaymentUpdateViewWeb(LoginRequiredMixin, View):
    """
    Payments are immutable ledger entries (Payment.save() rejects edits).
    This stub keeps the existing URL config working; remove the route when convenient.
    """

    def get(self, request, *args, **kwargs):
        messages.error(
            request,
            "Payments are permanent ledger entries and can't be edited. "
            "Record a correcting entry instead.",
        )
        return redirect("payment_list")

    post = get


# ============================================================================
# RENT CHARGES
# ============================================================================

class RentChargeListViewWeb(LoginRequiredMixin, ListView):
    model = RentCharge
    template_name = "rentcharges/rent_charge_list.html"
    context_object_name = "rentcharges"

    def get_queryset(self):
        return (
            RentCharge.objects.filter(user=self.request.user)
            .select_related("tenant")
            .order_by("-year", "-month")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tenants"] = Tenant.objects.filter(user=self.request.user)
        return context


class RentChargeDetailViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, DetailView):
    model = RentCharge
    template_name = "rentcharges/rentcharge_detail.html"
    context_object_name = "rentcharge"

    def get_queryset(self):
        return super().get_queryset().select_related("tenant")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payments"] = self.object.payments.order_by("-paid_at")
        return context


class RentChargeCreateViewWeb(LoginRequiredMixin, FormSaveMixin, CreateView):
    model = RentCharge
    fields = ["tenant", "year", "month", "amount_due"]
    template_name = "rentcharges/rentcharge_form.html"
    success_url = reverse_lazy("rent_charge_list")
    success_message = "Rent charge created successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["tenant"].queryset = Tenant.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class RentChargeUpdateViewWeb(LoginRequiredMixin, OwnedQuerysetMixin, FormSaveMixin, UpdateView):
    model = RentCharge
    form_class = RentChargeForm
    template_name = "rentcharges/rentcharge_form.html"
    success_url = reverse_lazy("rent_charge_list")
    success_message = "Rent charge updated successfully!"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["tenant"].queryset = Tenant.objects.filter(user=self.request.user)
        return form


@login_required
def bulk_create_rent_charges(request):
    today = timezone.localdate()

    active_tenants = list(
        Tenant.objects.filter(user=request.user, is_active=True, house__isnull=False)
        .select_related("house__flat_building")
        .order_by("full_name")
    )

    if request.method == "POST":
        month_raw = request.POST.get("month")
        year_raw = request.POST.get("year")
        tenant_ids_raw = request.POST.getlist("tenant_ids")

        if not month_raw or not year_raw:
            messages.error(request, "Please select month and year.")
            return redirect("rent_charge_bulk_create")
        if not tenant_ids_raw:
            messages.warning(request, "No tenants selected.")
            return redirect("rent_charge_bulk_create")

        try:
            month = int(month_raw)
            year = int(year_raw)
            tenant_ids = {int(tid) for tid in tenant_ids_raw}
        except ValueError:
            messages.error(request, "Invalid month, year, or tenant selection.")
            return redirect("rent_charge_bulk_create")

        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            messages.error(request, "Invalid month or year.")
            return redirect("rent_charge_bulk_create")

        # one query for the tenants, one for existing charges (was 2 queries per tenant)
        by_id = {t.pk: t for t in active_tenants if t.pk in tenant_ids}
        existing = set(
            RentCharge.objects.filter(tenant_id__in=by_id.keys(), year=year, month=month)
            .values_list("tenant_id", flat=True)
        )

        created_count = skipped_count = 0
        error_count = len(tenant_ids - set(by_id))   # not found, inactive, or someone else's

        for tenant in by_id.values():
            if tenant.pk in existing:
                skipped_count += 1
                continue
            try:
                with transaction.atomic():   # savepoint: one bad row can't poison the rest
                    RentCharge.objects.create(
                        user=request.user,
                        tenant=tenant,
                        year=year,
                        month=month,
                        amount_due=tenant.house.house_rent_amount,
                    )
                created_count += 1
            except (DjangoValidationError, IntegrityError):
                error_count += 1
                logger.exception("Could not create rent charge for tenant %s", tenant.pk)

        month_name = dict(RentCharge.MONTH_CHOICES).get(month, month)

        if created_count:
            messages.success(
                request, f"Successfully created {created_count} rent charge(s) for {month_name} {year}"
            )
            # bank payments that were waiting for a charge can be reconciled now
            try:
                freed = engine.rematch_pending(request.user)
                if freed:
                    messages.info(request, f"{freed} waiting bank payment(s) were reconciled automatically.")
            except Exception:
                logger.exception("Automatic reconciliation failed after bulk charge creation")
        if skipped_count:
            messages.info(request, f"Skipped {skipped_count} - charges already exist")
        if error_count:
            messages.error(request, f"Failed to create {error_count} charge(s)")

        return redirect("rent_charge_bulk_create")

    total_rent = sum((t.house.house_rent_amount for t in active_tenants), Decimal("0"))
    context = {
        "current_year": today.year,
        "current_month": today.month,
        "active_tenants": active_tenants,
        "active_tenants_count": len(active_tenants),
        "total_rent": total_rent,
        "months": RentCharge.MONTH_CHOICES,
        "years": range(today.year - 1, today.year + 2),
    }
    return render(request, "rentcharges/rentcharge_bulk_create.html", context)


# ============================================================================
# SMS REMINDERS
# ============================================================================

@login_required
def send_rent_reminders(request):
    """Manual trigger for sending rent reminders (own tenants only)."""
    tenants = Tenant.objects.filter(
        user=request.user, is_active=True, sms_notifications=True, house__isnull=False
    )

    if request.method == "POST":
        service = TwilioNotificationService()
        sent_count = failed_count = 0
        for tenant, rent_charge, days in reminder_candidates(tenants):
            success, _ = service.send_rent_due_reminder(rent_charge)
            if success:
                sent_count += 1
            else:
                failed_count += 1
        messages.success(request, f"Sent {sent_count} reminders. Failed: {failed_count}")
        return redirect("send_rent_reminders")

    tenants_to_remind = [
        {"tenant": t, "rent_charge": c, "days_until_due": d}
        for t, c, d in reminder_candidates(tenants)
    ]
    return render(request, "payments/send_sms.html", {
        "tenants_to_remind": tenants_to_remind,
        "today": timezone.localdate(),
    })