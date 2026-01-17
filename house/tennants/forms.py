from django import forms
from .models import House, Payment, Tenant, FlatBuilding, RentCharge
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm



class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(required=True, max_length=30)
    last_name = forms.CharField(required=True, max_length=30)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]


class HouseForm(forms.ModelForm):
    class Meta:
        model = House
        fields = '__all__'

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = '__all__'


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = '__all__'

class FlatBuildingForm(forms.ModelForm):
    class Meta:
        model = FlatBuilding
        fields = '__all__'

class RentChargeForm(forms.ModelForm):
    class Meta:
        model = RentCharge
        fields = '__all__'

# Additional forms can be added here as needed