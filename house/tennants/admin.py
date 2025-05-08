from django.contrib import admin
from .models import Tennant, House, RentPayment,FlatBuilding,PaymentHistory
from .forms import TennantForm
# Register your models here.

admin.site.register(Tennant)
admin.site.register(PaymentHistory)
admin.site.register(House)
admin.site.register(RentPayment)
admin.site.site_header = 'House Administration'

class HouseAdmin(admin.ModelAdmin):
    list_display = ["house_number", "building_name", "address", "occupation"]
    search_fields = ["house_number", "building_name"]
    list_filter = ["building_name", "occupation"]

    def prevent_delete_house(self, request, obj):
        if obj.occupation:
            self.message_user(request, "Cannot delete an occupied house.", level='error')
            return False
        return True

class TennantAdmin(admin.ModelAdmin):
    list_display = ["name", "house_number", "building_name", "address", "rent_status"]
    search_fields = ["name", "house_number", "building_name"]
    list_filter = ["building_name", "rent_status"]

class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ("__all__")

class FlatBuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'number_of_houses', 'how_many_occupied', 'vacant_houses')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)  # First, save the object to get a primary key
        obj.refresh_from_db()  # Ensure we have fresh data from the database
        obj.how_many_occupied = obj.houses.filter(occupation=True).count()
        obj.vacant_houses = obj.number_of_houses - obj.how_many_occupied
        obj.save()  # Save the updated fields

    def delete(self, request, obj):
        if obj.houses.filter(occupation=True).exists():
            self.message_user(request, "Cannot delete a flat building with occupied houses.", level='error')
            return False
        return True
admin.site.register(FlatBuilding, FlatBuildingAdmin)