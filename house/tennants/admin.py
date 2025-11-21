from django.contrib import admin
from .models import Tenant, House, RentPayment,FlatBuilding,PaymentHistory


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

@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ("user",'tenant', 'amount_paid', 'payment_date', 'year', 'rent_month', 'payment_method','is_paid', 'rent_amount', 'balance')
    list_filter = ('payment_date',)
    ordering = ('-payment_date',)
    readonly_fields = ('rent_amount', 'balance',)

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


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ("user",'tenant', 'house', 'payment_amount', 'payment_date', 'payment_method')
    list_filter = ('payment_date',)
    ordering = ('-payment_date',)

    def save_model(self, request, obj, form, change):
        obj.auto_set_fields()
        super().save_model(request, obj, form, change)