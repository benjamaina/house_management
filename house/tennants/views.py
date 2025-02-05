from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, generics
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .models import Tennant, House, RentPayment
from .serializers import TennantSerializer, HouseSerializer,RentPaymentSerializer
import logging
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login

logger = logging.getLogger(__name__)

# Tenant Management Views
class TenantListView(generics.ListCreateAPIView):
    queryset = Tennant.objects.all()
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
        tenant = serializer.save()

        try:
            house.assign_tenant_to_house(tenant)
        except ValidationError as e:
            logger.error(str(e))
            raise serializers.ValidationError(str(e))

class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tennant.objects.all()
    serializer_class = TennantSerializer
    permission_classes = [IsAuthenticated]

# House Management Views
class HouseListView(generics.ListCreateAPIView):
    queryset = House.objects.all()
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]

class HouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = House.objects.all()
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]

# Rent Payment Views
class RentPaymentListView(generics.ListCreateAPIView):
    queryset = RentPayment.objects.all()
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

class RentPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = RentPayment.objects.all()
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

# # Custom Login View
# @csrf_exempt
# def custom_login(request):
#     if request.method == "POST":
#         username = request.POST.get("username")
#         password = request.POST.get("password")
#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             login(request, user)
#             next_url = request.GET.get('next', '/admin/')  # Redirect to the next URL if provided, otherwise to the dashboard 
#             return redirect(next_url)  # Redirect to a dashboard or home page
#         else:
#             return render(request, "login.html", {"error": "Invalid credentials"})

#     return render(request, "login.html")

# MPesa Payment API Integration
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
        tenant = Tennant.objects.get(id=tenant_id)
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
