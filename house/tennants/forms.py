from django import forms
from .models import Tennant, House, RentPayment

class TennantForm(forms.ModelForm):
    class Meta:
        model = Tennant
        fields = '__all__'

class HouseForm(forms.ModelForm):
    class Meta:
        model = House
        fields = '__all__'

class RentPaymentForm(forms.ModelForm):
    class Meta:
        model = RentPayment
        fields = '__all__'

class TennantForm(forms.ModelForm):
    class Meta:
        model = Tennant
        fields = '__all__'