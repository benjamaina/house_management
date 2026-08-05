from rest_framework import serializers
from .models import Tenant, House, Payment, FlatBuilding, RentCharge
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()





class TenantSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Tenant
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and 'house' in self.fields:
            self.fields['house'].queryset = House.objects.filter(user=request.user)

class HouseSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = House
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and 'flat_building' in self.fields:
            self.fields['flat_building'].queryset = FlatBuilding.objects.filter(user=request.user)

    def validate(self, attrs):
        building = attrs.get('flat_building')
        if building and building.houses.count() >= building.capacity:
            raise serializers.ValidationError(
                f"Cannot add house. {building.building_name} can only have {building.capacity} houses."
            )
        return attrs
    
class FlatBuildingSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = FlatBuilding
        fields = '__all__'
        search_fields = ['building_name']



class PaymentSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Payment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request:            
            if 'tenant' in self.fields:
                self.fields['tenant'].queryset = Tenant.objects.filter(user=request.user)
            if 'rent_charge' in self.fields:
                self.fields['rent_charge'].queryset = RentCharge.objects.filter(user=request.user)
            
class RegisterAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name']

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        user.set_password(validated_data['password'])
        user.is_staff = True
        user.save()
        return user

class ForgotPasswordSerializer(serializers.Serializer):
    username = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    otp = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def save(self):
        username = self.validated_data['username']
        new_password = self.validated_data['new_password']
        otp = self.validated_data['otp']

        user = User.objects.get(username=username)

        # TODO: validate OTP here

        user.set_password(new_password)
        user.save()
        return user


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)
    token = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    def validate(self, data):
        from django.contrib.auth import authenticate
        from rest_framework_simplejwt.tokens import RefreshToken

        username = data.get('username')
        password = data.get('password')
        user = authenticate(username=username, password=password)

        if user is None or not user.is_staff:
            raise serializers.ValidationError("Invalid credentials or not an admin user")

        refresh = RefreshToken.for_user(user)
        data['token'] = str(refresh.access_token)
        data['refresh'] = str(refresh)
        return data

class RentChargeSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = RentCharge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and 'tenant' in self.fields:
            self.fields['tenant'].queryset = Tenant.objects.filter(user=request.user)