from django.contrib import admin
from .models import Tenant, House, Payment,FlatBuilding,RentCharge
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

admin.site.site_header = 'House Administration'


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):

    list_display = ('user','full_name', 'email', 'phone', 'house', 'rent', 'security_deposit', 'balance','building_name')
    ordering = ('full_name',)
    readonly_fields = ('rent', 'security_deposit', 'balance','user')

    def deposit_amount(self, obj):
        return obj.security_deposit
    deposit_amount.short_description = 'Security Deposit'

    def building_name(self, obj):
        return obj.building_name
    building_name.short_description = 'Building Name'

    def rent_amount(self, obj):
        return obj.rent
    rent_amount.short_description = 'Monthly Rent'


    def save_model(self, request, obj, form, change):
        # Automatically set rent and security deposit from the associated house
        super().save_model(request, obj, form, change)

@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display = ('house_number', 'flat_building', 'house_size', 'house_rent_amount', 'deposit_amount', 'occupation')
    readonly_fields = ( 'occupation',)
    list_filter = ('flat_building', 'occupation')
    search_fields = ('house_number', 'flat_building__building_name')


    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'payment_method','paid_at', 'rent_charge', 'payment_reference',"amount")
    readonly_fields = ('amount', 'balance',)

    def house(self, obj):
        return obj.tenant.house.house_number if obj.tenant and obj.tenant.house else None

    def balance(self, obj):
        return obj.balance
    balance.short_description = 'Balance'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(FlatBuilding)
class FlatBuildingAdmin(admin.ModelAdmin):
    list_display = ('user','building_name', 'address', 'number_of_houses', 'how_many_occupied', 'vacant_houses','tenant_count')
    search_fields = ('biulding_name', 'address')
    readonly_fields = ('how_many_occupied', 'vacant_houses')

    def how_many_occupied(self, obj):
        return obj.how_many_occupied
    how_many_occupied.short_description = 'Occupied Houses'

    def tenant_count(self, obj):
        return obj.tenant_count()
    tenant_count.short_description = 'Number of Tenants'


    def vacant_houses(self, obj):
        return obj.vacant_houses
    vacant_houses.short_description = 'Vacant Houses'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(RentCharge)
class RentChargeAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'year', 'is_paid', 'month', 'amount_due')
    list_filter = ('month', 'year')
    ordering = ('-year',)
    search_fields = ('tenant__full_name',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)