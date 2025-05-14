from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, generics
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .models import Tennant, House, RentPayment,FlatBuilding
from .serializers import TennantSerializer, HouseSerializer,RentPaymentSerializer, AdminLoginSerializer,RegisterAdminSerializer,FlatBuildingSerializer,RentPaymentSerializer
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
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken

# import allowany


logger = logging.getLogger(__name__)

class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tennant.objects.all()
    serializer_class = TennantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        house_id = self.request.query_params.get('house_id')
        if house_id:
            queryset = queryset.filter(house_id=house_id, user=self.request.user)
        return queryset
    
    def get_object(self):
        obj = super().get_object()
        if obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to access this resource.")
        return obj


class TenantListView(generics.ListCreateAPIView):
    queryset = Tennant.objects.all().order_by('id')
    serializer_class = TennantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_active', 'house', 'name']
    ordering_fields = ['name', 'created_at']

    def perform_create(self, serializer):
        house = serializer.validated_data['house']
        if house.tennants.count() >= house.flat_building.number_of_houses:
            logger.error('House is full')
            raise serializers.ValidationError('House is full')
        tenant = serializer.save(user =self.request.user)
        return tenant

    def get_queryset(self):
        return Tennant.objects.filter(is_active=True,user=self.request.user).order_by('id')


class HouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = House.objects.all()
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_object(self):
        obj = super().get_object()
        if obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to access this resource.")
        return obj

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        flat_building_id = self.request.query_params.get('flat_building_id')
        if flat_building_id:
            queryset = queryset.filter(flat_building_id=flat_building_id, user=self.request.user).order_by('id')
        return queryset 
            
class HouseListView(generics.ListCreateAPIView):

    queryset = House.objects.all().order_by('id')
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['house_num', 'house_size', 'house_rent_amount']

    def perform_create(self, serializer):
        flat_building = serializer.validated_data['flat_building']
        if flat_building.houses.count() >= flat_building.number_of_houses:
            logger.error('FlatBuilding is full')
            raise serializers.ValidationError('FlatBuilding is full')
        house = serializer.save(user=self.request.user)
        return house

    def get_queryset(self):
        queryset = super().get_queryset()
        flat_building_id = self.request.query_params.get('flat_building_id')
        if flat_building_id:
            queryset = queryset.filter(flat_building_id=flat_building_id, user=self.request.user).order_by('id')
        return queryset

    def get_queryset(self):
        return House.objects.filter(user=self.request.user).order_by('id')

class RentPaymentListView(generics.ListCreateAPIView):
    queryset = RentPayment.objects.all().order_by('id')
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        tennant = serializer.validated_data['tennant']
        rent_payment = serializer.save(user=self.request.user)

        if rent_payment.is_paid:
            tennant.balance -= rent_payment.amount
            tennant.save()

        return rent_payment

    def get_queryset(self):
        return RentPayment.objects.filter(is_paid=True, user=self.request.user).order_by('id')

class RentPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RentPayment.objects.all()
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        tennant_id = self.request.query_params.get('tennant_id')
        if tennant_id:
            queryset = queryset.filter(tennant_id=tennant_id, user=self.request.user)
        return queryset


    def get_object(self):
        obj = super().get_object()
        if obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to access this resource.")
        return obj


class FlatBuildingListView(generics.ListCreateAPIView):
    queryset = FlatBuilding.objects.all().order_by('id')
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        flat_building = serializer.save(user=self.request.user)
        return flat_building


    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name, user=self.request.user).order_by('id')
        return queryset


    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user).order_by('id')


class FlatBuildingDetailView(generics.DestroyAPIView):
    queryset = FlatBuilding.objects.all()
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk' 
    

    def get_object(self):
        pk = self.kwargs.get('pk')
        if pk:
            return super().get_object()  
        return FlatBuilding()
    
    def destroy(self, request, *args, **kwargs):
        flat_building = self.get_object()
        if flat_building.houses.exists():
            return Response({"message": "Cannot delete FlatBuilding with existing houses."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name, user=self.request.user).order_by('id')
        return queryset

    def perform_create(self, serializer):
        flat_building = serializer.save(user=self.request.user)
        return flat_building

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_login(request):
    logger.debug(f"Admin login attempt with data: {request.data}")
    serializer = AdminLoginSerializer(data=request.data)  # Consistent with 'serializer'
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        logger.debug(f"Attempting to authenticate user: {username}")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token  # Fixed typo

            return Response({
                "message": "Login successful",
                "access_token": str(access_token),  # Return correct access token
                "refresh_token": str(refresh),
            }, status=status.HTTP_200_OK)
        else:
            logger.debug(f"Authentication failed for user: {username}")
            return Response({
                "message": "Invalid credentials or not a superuser",
            }, status=status.HTTP_401_UNAUTHORIZED)
    else:
        logger.debug(f"Serializer errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
class RegisterAdminView(APIView):
    permission_classes = [permissions.AllowAny]  # You can lock this down later

    def post(self, request):
        serializer = RegisterAdminSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            email = serializer.validated_data.get('email', '')

            try:
                User.objects.create_superuser(username=username, password=password, email=email)
                return Response({"message": "Admin registered successfully."}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class AdminLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Blacklist the refresh token
            RefreshToken(request.data['refresh_token']).blacklist()
            return Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def mpesa_payment_notification(request):
    logger.info(f"Received data: {request.data}")
    payment_data = request.data
    
    try:
        rent_payment_id = payment_data.get('rent_payment_id')
        payment_status = payment_data.get('payment_status')
        
        rent_payment = RentPayment.objects.get(id=rent_payment_id)
        
        if payment_status == 'SUCCESS':
            rent_payment.is_paid = True
            rent_payment.save()
            return Response({"message": "Payment updated successfully"}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Payment failed"}, status=status.HTTP_400_BAD_REQUEST)
    
    except RentPayment.DoesNotExist:
        logger.error(f"RentPayment with ID {rent_payment_id} does not exist.")
        return Response({"message": "Rent payment not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return Response({"message": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def mpesa_payment(request):
    if request.method == "POST":
        tenant_id = request.POST.get('tenant_id')
        try:
            tenant = Tennant.objects.get(id=tenant_id)
        except Tennant.DoesNotExist:
            return JsonResponse({"message": "Tenant not found"}, status=404)
        rent_amount = tenant.house.house_rent_amount

        mpesa_url = "https://sandbox.safaricom.co.ke/mpesa/lnmo/paymentrequest"
        headers = {
            'Authorization': 'Bearer ' + get_mpesa_token(),
            'Content-Type': 'application/json',
        }
        payload = {
            "Initiator": settings.MPESA_INITIATOR,
            "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
            "LipaNaMpesaOnlineShortcode": settings.MPESA_SHORTCODE,
            "PhoneNumber": tenant.phone,
            "Amount": rent_amount,
            "AccountReference": f"Rent for {tenant.house}",
            "TransactionDesc": "Rent Payment"
        }
        response = requests.post(mpesa_url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({"message": "Payment request initiated successfully"}, status=200)
        else:
            return JsonResponse({"message": "Error initiating payment"}, status=500)

    return JsonResponse({"message": "Invalid request method"}, status=400)
