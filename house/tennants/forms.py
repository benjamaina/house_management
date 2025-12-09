from django import forms
from .models import House, RentPayment, Tenant, FlatBuilding, PaymentHistory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm



class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']



class HouseForm(forms.ModelForm):
    class Meta:
        model = House
        fields = '__all__'

class RentPaymentForm(forms.ModelForm):
    class Meta:
        model = RentPayment
        fields = '__all__'


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = '__all__'

class FlatBuildingForm(forms.ModelForm):
    class Meta:
        model = FlatBuilding
        fields = '__all__'

class PaymentHistoryForm(forms.ModelForm):
    class Meta:
        model = PaymentHistory
        fields = '__all__'

# Additional forms can be added here as needed