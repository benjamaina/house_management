# this views are for returning html pages
# Add these to your existing views.py (keep your API views too!)

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render
from django.core.exceptions import ValidationError
from .models import Tenant, House, RentPayment, FlatBuilding

# ============================================================================
# WEB TEMPLATE VIEWS (for normal users in browser)
# ============================================================================

# Dashboard
@login_required
def dashboard(request):
    """Main dashboard showing summary stats"""
    buildings = FlatBuilding.objects.filter(user=request.user)
    total_houses = House.objects.filter(user=request.user).count()
    occupied_houses = House.objects.filter(user=request.user, occupation=True).count()
    active_tenants = Tenant.objects.filter(user=request.user, is_active=True).count()
    
    # Recent payments (last 5)
    recent_payments = RentPayment.objects.filter(
        user=request.user
    ).order_by('-payment_date')[:5]
    
    context = {
        'buildings': buildings,
        'total_houses': total_houses,
        'occupied_houses': occupied_houses,
        'vacant_houses': total_houses - occupied_houses,
        'active_tenants': active_tenants,
        'recent_payments': recent_payments,
    }
    return render(request, 'dashboard.html', context)


# ============================================================================
# BUILDING VIEWS
# ============================================================================

class BuildingListView(LoginRequiredMixin, ListView):
    model = FlatBuilding
    template_name = 'buildings/building_list.html'
    context_object_name = 'buildings'
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)


class BuildingCreateView(LoginRequiredMixin, CreateView):
    model = FlatBuilding
    fields = ['building_name', 'address', 'number_of_houses']
    template_name = 'buildings/building_form.html'
    success_url = reverse_lazy('building_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Building created successfully!')
        return super().form_valid(form)


class BuildingUpdateView(LoginRequiredMixin, UpdateView):
    model = FlatBuilding
    fields = ['building_name', 'address', 'number_of_houses']
    template_name = 'buildings/building_form.html'
    success_url = reverse_lazy('building_list')
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Building updated successfully!')
        return super().form_valid(form)


class BuildingDeleteView(LoginRequiredMixin, DeleteView):
    model = FlatBuilding
    template_name = 'buildings/building_confirm_delete.html'
    success_url = reverse_lazy('building_list')
    
    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Building deleted successfully!')
        return super().delete(request, *args, **kwargs)


class BuildingDetailView(LoginRequiredMixin, DetailView):
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

class HouseListView(LoginRequiredMixin, ListView):
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


class HouseCreateView(LoginRequiredMixin, CreateView):
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


class HouseUpdateView(LoginRequiredMixin, UpdateView):
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


class HouseDeleteView(LoginRequiredMixin, DeleteView):
    model = House
    template_name = 'houses/house_confirm_delete.html'
    success_url = reverse_lazy('house_list')
    
    def get_queryset(self):
        return House.objects.filter(user=self.request.user)


class HouseDetailView(LoginRequiredMixin, DetailView):
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

class TenantListView(LoginRequiredMixin, ListView):
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


class TenantCreateView(LoginRequiredMixin, CreateView):
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


class TenantUpdateView(LoginRequiredMixin, UpdateView):
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


class TenantDeleteView(LoginRequiredMixin, DeleteView):
    model = Tenant
    template_name = 'tenants/tenant_confirm_delete.html'
    success_url = reverse_lazy('tenant_list')
    
    def get_queryset(self):
        return Tenant.objects.filter(user=self.request.user)


class TenantDetailView(LoginRequiredMixin, DetailView):
    model = Tenant
    template_name = 'tenants/tenant_detail.html'
    context_object_name = 'tenant'
    
    def get_queryset(self):
        return Tenant.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get payment history
        context['payments'] = self.object.rent_payments.all().order_by('-payment_date')
        context['overdue_payments'] = self.object.rent_payments.filter(is_paid=False)
        return context


# ============================================================================
# PAYMENT VIEWS
# ============================================================================

class PaymentListView(LoginRequiredMixin, ListView):
    model = RentPayment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    
    def get_queryset(self):
        return RentPayment.objects.filter(user=self.request.user).order_by('-payment_date')


class PaymentCreateView(LoginRequiredMixin, CreateView):
    model = RentPayment
    fields = ['tenant', 'rent_month', 'year', 'amount_paid', 'payment_method']
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payment_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Only show active tenants
        form.fields['tenant'].queryset = Tenant.objects.filter(
            user=self.request.user, 
            is_active=True
        )
        return form
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Payment recorded successfully!')
        return super().form_valid(form)


class OverduePaymentsView(LoginRequiredMixin, ListView):
    model = RentPayment
    template_name = 'payments/overdue_payments.html'
    context_object_name = 'overdue_payments'
    
    def get_queryset(self):
        return RentPayment.objects.filter(
            user=self.request.user,
            is_paid=False
        ).order_by('year', 'rent_month')