from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, generics
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from tennants.models import Tenant, House, Payment, FlatBuilding, RentCharge
from tennants.serializers import (TenantSerializer, HouseSerializer, PaymentSerializer,
                          FlatBuildingSerializer, RegisterAdminSerializer, AdminLoginSerializer, ForgotPasswordSerializer)
import logging
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework.decorators import permission_classes

from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework_simplejwt.tokens import RefreshToken
import hashlib
import json
import logging
from tennants.forms import RegistrationForm
from django.shortcuts import render, redirect
from django.db import transaction

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render
from django.core.exceptions import ValidationError
from django.utils import timezone
from tennants.services.sms import TwilioNotificationService




logger = logging.getLogger(__name__)


# this views are for returning html pages
# ============================================================================
# WEB TEMPLATE VIEWS (for normal users in browser)
# ============================================================================

# landing page
def landing_page(request):
    """Render the landing page"""
    return render(request, 'landing.html')

# view to change passowrd for normal users
class ForgotPasswordViewWeb(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        

# Dashboard
@login_required
def dashboard(request):
    """Main dashboard showing summary stats"""
    buildings = FlatBuilding.objects.filter(user=request.user)
    total_houses = House.objects.filter(user=request.user).count()
    occupied_houses = House.objects.filter(user=request.user, occupation=True).count()
    active_tenants = Tenant.objects.filter(user=request.user, is_active=True).count()
    
    # Recent payments (last 5)
    recent_payments = Payment.objects.filter(
        user=request.user
    ).order_by('-paid_at')[:5]
    
    # Calculate percentage of occupied houses (avoid division by zero)
    if total_houses:
        percent_occupied = round((occupied_houses / total_houses) * 100, 2)
    else:
        percent_occupied = 0.0
    
    context = {
        'buildings': buildings,
        'total_houses': total_houses,
        'occupied_houses': occupied_houses,
        'vacant_houses': total_houses - occupied_houses,
        'active_tenants': active_tenants,
        'recent_payments': recent_payments,
        'percent_occupied': percent_occupied,
    }
    return render(request, 'dashboard.html', context)


# ============================================================================
# BUILDING VIEWS
# ============================================================================

class BuildingListViewWeb(LoginRequiredMixin, ListView):
    model = FlatBuilding
    template_name = 'buildings/building_list.html'
    context_object_name = 'buildings'
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)


class BuildingCreateViewWeb(LoginRequiredMixin, CreateView):
    model = FlatBuilding
    fields = ['building_name', 'address', 'number_of_houses']
    template_name = 'buildings/building_form.html'
    success_url = reverse_lazy('building_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Building created successfully!')
        return super().form_valid(form)


class BuildingUpdateViewWeb(LoginRequiredMixin, UpdateView):
    model = FlatBuilding
    fields = ['building_name', 'address', 'number_of_houses']
    template_name = 'buildings/building_form.html'
    success_url = reverse_lazy('building_list')
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Building updated successfully!')
        return super().form_valid(form)


class BuildingDeleteViewWeb(LoginRequiredMixin, DeleteView):
    model = FlatBuilding
    template_name = 'buildings/building_confirm_delete.html'
    success_url = reverse_lazy('building_list')
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        # first check if building has houses and those houses have tenants
        building = self.get_object()
        if building.houses.filter(occupation=True).exists():
            messages.error(self.request, 'Cannot delete building with occupied houses!')
            return redirect('building_list')
        messages.success(self.request, 'Building deleted successfully!')
        return super().delete(request, *args, **kwargs)
        

class BuildingDetailViewWeb(LoginRequiredMixin, DetailView):
    model = FlatBuilding
    template_name = 'buildings/building_detail.html'
    context_object_name = 'building'
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all houses in this building
        context['houses'] = self.object.houses.all()
        return context


# ============================================================================
# HOUSE VIEWS
# ============================================================================

class HouseListViewWeb(LoginRequiredMixin, ListView):
    model = House
    template_name = 'houses/house_list.html'
    context_object_name = 'houses'
    
    def get_queryset(self):
        queryset = House.objects.filter(user=self.request.user)
        # Optional filter by building
        building_id = self.request.GET.get('building')
        if building_id:
            queryset = queryset.filter(flat_building_id=building_id)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['buildings'] = FlatBuilding.objects.filter(user=self.request.user)
        return context


class HouseCreateViewWeb(LoginRequiredMixin, CreateView):
    model = House
    fields = ['flat_building', 'house_number', 'house_size', 'house_rent_amount', 'deposit_amount']
    template_name = 'houses/house_form.html'
    success_url = reverse_lazy('house_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show user's buildings in dropdown
        form.fields['flat_building'].queryset = FlatBuilding.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            messages.success(self.request, 'House created successfully!')
            return super().form_valid(form)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class HouseUpdateViewWeb(LoginRequiredMixin, UpdateView):
    model = House
    fields = ['flat_building', 'house_number', 'house_size', 'house_rent_amount', 'deposit_amount']
    template_name = 'houses/house_form.html'
    success_url = reverse_lazy('house_list')
    
    def get_queryset(self):
        return House.objects.filter(user=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['flat_building'].queryset = FlatBuilding.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'House updated successfully!')
        return super().form_valid(form)


class HouseDeleteViewWeb(LoginRequiredMixin, DeleteView):
    model = House
    template_name = 'houses/house_confirm_delete.html'
    success_url = reverse_lazy('house_list')
    
    def get_queryset(self):
        return House.objects.filter(user=self.request.user)


class HouseDetailViewWeb(LoginRequiredMixin, DetailView):
    model = House
    template_name = 'houses/house_detail.html'
    context_object_name = 'house'
    
    def get_queryset(self):
        return House.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get current tenant if any
        context['tenant'] = self.object.tenants.filter(is_active=True).first()
        return context


# ============================================================================
# TENANT VIEWS
# ============================================================================

class TenantListViewWeb(LoginRequiredMixin, ListView):
    model = Tenant
    template_name = 'tenants/tenant_list.html'
    context_object_name = 'tenants'
    
    def get_queryset(self):
        queryset = Tenant.objects.filter(user=self.request.user)
        # Optional filter by active status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset


class TenantCreateViewWeb(LoginRequiredMixin, CreateView):
    model = Tenant
    fields = ['full_name', 'email', 'phone', 'id_number', 'house', 'rent_due_date']
    template_name = 'tenants/tenant_form.html'
    success_url = reverse_lazy('tenant_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show vacant houses
        form.fields['house'].queryset = House.objects.filter(
            user=self.request.user, 
            occupation=False
        )
        return form
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        try:
            messages.success(self.request, 'Tenant added successfully!')
            return super().form_valid(form)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class TenantUpdateViewWeb(LoginRequiredMixin, UpdateView):
    model = Tenant
    fields = ['full_name', 'email', 'phone', 'id_number', 'house', 'rent_due_date', 'is_active']
    template_name = 'tenants/tenant_form.html'
    success_url = reverse_lazy('tenant_list')
    
    def get_queryset(self):
        return Tenant.objects.filter(user=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Show all user's houses
        form.fields['house'].queryset = House.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Tenant updated successfully!')
        return super().form_valid(form)


class TenantDeleteViewWeb(LoginRequiredMixin, DeleteView):
    model = Tenant
    template_name = 'tenants/tenant_confirm_delete.html'
    success_url = reverse_lazy('tenant_list')
    
    def get_queryset(self):
        return Tenant.objects.filter(user=self.request.user)


class TenantDetailViewWeb(LoginRequiredMixin, DetailView):
    model = Tenant
    template_name = 'tenants/tenant_detail.html'
    context_object_name = 'tenant'
    
    def get_queryset(self):
        return Tenant.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get payment history
        context['payments'] = self.object.payments.all().order_by('-paid_at')
        # context['overdue_payments'] = self.object.rent_payments.filter(is_paid=False)
        return context


# ============================================================================
# PAYMENT VIEWS
# ============================================================================
class PaymentDetailViewWeb(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class PaymentUpdateViewWeb(LoginRequiredMixin, UpdateView):
    model = Payment
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payment_list')
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show user's tenants
        form.fields['tenant'].queryset = Tenant.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Payment updated successfully!')
        return super().form_valid(form)

class PaymentListViewWeb(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    
    def get_queryset(self):
        queryset = Payment.objects.filter(user=self.request.user)
        # Optional filter by tenant
        tenant_id = self.request.GET.get('tenant')
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by('-paid_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenants'] = Tenant.objects.filter(user=self.request.user)
        return context

class PaymentCreateViewWeb(LoginRequiredMixin, CreateView):
    model = Payment
    fields = [
        "tenant",
        "rent_charge",
        "amount",
        "payment_reference",
        "payment_method",
    ]
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payment_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show user's tenants
        form.fields['tenant'].queryset = Tenant.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Payment recorded successfully!')
        return super().form_valid(form)
    
class RentChargeCreateViewWeb(LoginRequiredMixin, CreateView):
    model = RentCharge
    fields = ['tenant', 'year', 'month', 'amount_due']
    template_name = 'rentcharges/rentcharge_form.html'
    success_url = reverse_lazy('rent_charge_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show user's tenants
        form.fields['tenant'].queryset = Tenant.objects.filter(user=self.request.user)
        return form
    
 

class RentChargeDetailViewWeb(LoginRequiredMixin, DetailView):
    model = RentCharge
    template_name = 'rentcharges/rentcharge_detail.html'
    context_object_name = 'rentcharge'
    
    def get_queryset(self):
        return RentCharge.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    


class RentChargeListViewWeb(LoginRequiredMixin, ListView):
    model = RentCharge
    template_name = 'rentcharges/rent_charge_list.html'
    context_object_name = 'rentcharges'

    # display only rent charges for current user
    def get_queryset(self):
        return RentCharge.objects.filter(user=self.request.user).order_by('-year', '-month')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenants'] = Tenant.objects.filter(user=self.request.user)
        return context


class RentChargeUpdateViewWeb(LoginRequiredMixin, UpdateView):
    model = RentCharge
    template_name = 'rentcharges/rentcharge_form.html'
    success_url = reverse_lazy('rent_charge_list')
    
    def get_queryset(self):
        return RentCharge.objects.filter(user=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show user's tenants
        form.fields['tenant'].queryset = Tenant.objects.filter(user=self.request.user)
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Rent charge updated successfully!')
        return super().form_valid(form)


@login_required
def bulk_create_rent_charges(request):
    current_year = timezone.now().year
    current_month = timezone.now().month

    # Filter by current user
    active_tenants = Tenant.objects.filter(
        user=request.user, 
        is_active=True,
        house__isnull=False  # Only tenants with houses
    ).select_related("house")

    active_tenants_count = active_tenants.count()

    # Calculate expected total rent safely
    total_rent = sum(
        tenant.house.house_rent_amount
        for tenant in active_tenants
        if tenant.house
    )

    if request.method == "POST":
        month = request.POST.get("month")
        year = request.POST.get("year")
        tenant_ids = request.POST.getlist("tenant_ids")

        if not month or not year:
            messages.error(request, "Please select month and year.")
            return redirect("rent_charge_bulk_create")  # ✅ Fixed: use URL name

        if not tenant_ids:
            messages.warning(request, "No tenants selected.")
            return redirect("rent_charge_bulk_create")  # ✅ Fixed: use URL name

        # Convert to integers
        try:
            month = int(month)
            year = int(year)
            tenant_ids = [int(tid) for tid in tenant_ids]
        except ValueError:
            messages.error(request, "Invalid month, year, or tenant selection.")
            return redirect("rent_charge_bulk_create")  # ✅ Fixed: use URL name

        # Create rent charges
        created_count = 0
        skipped_count = 0
        error_count = 0

        with transaction.atomic():
            for tenant_id in tenant_ids:
                try:
                    tenant = Tenant.objects.get(id=tenant_id, user=request.user)
                    
                    # Check if already exists
                    if RentCharge.objects.filter(
                        tenant=tenant,
                        year=year,
                        month=month
                    ).exists():
                        skipped_count += 1
                        continue
                    
                    # Create rent charge
                    RentCharge.objects.create(
                        user=request.user,
                        tenant=tenant,
                        year=year,
                        month=month,
                        amount_due=tenant.house.house_rent_amount
                    )
                    created_count += 1
                    
                except Tenant.DoesNotExist:
                    error_count += 1
                    logger.error(f"Tenant {tenant_id} not found for user {request.user.id}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error creating rent charge for tenant {tenant_id}: {str(e)}")

        # Success messages
        month_name = dict(RentCharge.MONTH_CHOICES).get(month, month)
        
        if created_count > 0:
            messages.success(
                request, 
                f"✓ Successfully created {created_count} rent charge(s) for {month_name} {year}"
            )
        if skipped_count > 0:
            messages.info(
                request, 
                f"⊘ Skipped {skipped_count} - charges already exist"
            )
        if error_count > 0:
            messages.error(
                request, 
                f"✗ Failed to create {error_count} charge(s)"
            )
        
        return redirect("rent_charge_bulk_create")  # ✅ Fixed: use URL name

    context = {
        "current_year": current_year,
        "current_month": current_month,
        "active_tenants": active_tenants,
        "active_tenants_count": active_tenants_count,
        "total_rent": total_rent,
        "months": RentCharge.MONTH_CHOICES,
        "years": range(current_year - 1, current_year + 2),
    }

    return render(request, "rentcharges/rentcharge_bulk_create.html", context)



@login_required
def send_rent_reminders(request):
    """Manual trigger for sending rent reminders"""
    if request.method == 'POST':
        notification_service = TwilioNotificationService()
        today = timezone.now().date()
        sent_count = 0
        failed_count = 0
        
        # Get all active tenants with SMS enabled
        active_tenants = Tenant.objects.filter(
            is_active=True, 
            sms_notifications=True
        )
        
        for tenant in active_tenants:
            days_until_due = (tenant.rent_due_date - today).days
            
            # Check if reminder should be sent
            if 0 <= days_until_due <= tenant.reminder_days_before:
                try:
                    rent_charge = RentCharge.objects.get(
                        tenant=tenant,
                        year=today.year,
                        month=today.month
                    )
                    
                    if not rent_charge.reminder_sent:
                        success, result = notification_service.send_rent_due_reminder(rent_charge)
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                            
                except RentCharge.DoesNotExist:
                    pass
        
        messages.success(request, f'✓ Sent {sent_count} reminders. Failed: {failed_count}')
        return redirect('send_rent_reminders')
    
    # GET request - show preview
    today = timezone.now().date()
    tenants_to_remind = []
    
    active_tenants = Tenant.objects.filter(
        is_active=True, 
        sms_notifications=True
    )
    
    for tenant in active_tenants:
        days_until_due = (tenant.rent_due_date - today).days
        
        if 0 <= days_until_due <= tenant.reminder_days_before:
            try:
                rent_charge = RentCharge.objects.get(
                    tenant=tenant,
                    year=today.year,
                    month=today.month
                )
                
                if not rent_charge.reminder_sent:
                    tenants_to_remind.append({
                        'tenant': tenant,
                        'rent_charge': rent_charge,
                        'days_until_due': days_until_due,
                    })
            except RentCharge.DoesNotExist:
                pass
    
    context = {
        'tenants_to_remind': tenants_to_remind,
        'today': today,
    }

    return render(request, 'payments/send_sms.html', context)