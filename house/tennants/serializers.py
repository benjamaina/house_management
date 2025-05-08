from rest_framework import serializers
from .models import Tennant, House, RentPayment, FlatBuilding
from django.contrib.auth.models import User

class RegisterAdminSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if not username or not password:
            raise serializers.ValidationError("Username and password are required.")

        return attrs

class TenantLogoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tennant
        fields = ['id','name', 'phone', 'id_number', 'house', 'is_active',"user"]

class FlatBuildingSerializer(serializers.ModelSerializer):
    how_many_occupied = serializers.IntegerField(read_only=True)
    vacant_houses = serializers.IntegerField(read_only=True)

    class Meta:
        model = FlatBuilding
        fields = ['id', 'name', 'address', 'number_of_houses', 'how_many_occupied', 'vacant_houses','user']

class RentPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentPayment
        fields = ["id",'tennant','amount', 'payment_date', 'rent_month', 'is_paid',"created_at", 'updated_at', "user"]
        read_only_fields = ['created_at', 'updated_at'] 

class TennantSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    outstanding_rent = serializers.SerializerMethodField()

    class Meta:
        model = Tennant
        fields = ['id','name', 'phone', 'balance', 'id_number', 'house', 'is_active', 'outstanding_rent',"user"]
        read_only_fields = ['balance', 'outstanding_rent']

    def get_outstanding_rent(self, obj):
        return obj.outstanding_rent()


    def validate(self, attrs):
        house = attrs.get('house')  # Correctly use attrs to access data
        is_active = attrs.get('is_active', True)

        if is_active and house.tennants.filter(is_active=True).exists():
            raise serializers.ValidationError("House is already occupied by another tenant.")

        return attrs  # Return the validated attributes
class HouseSerializer(serializers.ModelSerializer):
    flat_building_name = serializers.CharField(source='flat_building.name', read_only=True)
    class Meta:
        model = House
        fields = ['id', 'house_num', 'house_size', 'house_rent_amount', "occupation", 'flat_building', 'flat_building_name',"user"]
        read_only_fields = ['occupation']
