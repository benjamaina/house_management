from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, generics
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .models import Tenant, House, RentPayment, FlatBuilding
from .serializers import (TenantSerializer, HouseSerializer, RentPaymentSerializer,
                          FlatBuildingSerializer, RegisterAdminSerializer, AdminLoginSerializer)
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
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework_simplejwt.tokens import RefreshToken
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

CACHE_TTL = getattr(settings, 'CACHE_TTL', 60 * 15)

def make_cache_key(request, prefix=""):
    user_id = getattr(request.user, 'id', 'anonymous')
    key = f"{prefix}:{user_id}:{request.get_full_path()}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()

def get_cached_response(request, prefix=""):
    key = make_cache_key(request, prefix)
    return cache.get(key)

def set_cached_response(request, data, prefix=""):
    key = make_cache_key(request, prefix)
    cache.set(key, data, CACHE_TTL)

def clear_cache_pattern(request, prefix=""):
    cache.delete_pattern(f"*{prefix}*")


# ============================================================================
# TENANT VIEWS
# ============================================================================

class TenantListView(generics.ListCreateAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_active', 'house', 'full_name']
    ordering_fields = ['full_name', 'created_at']

    def get_queryset(self):
        """Filter tenants to only show current user's tenants"""
        return Tenant.objects.filter(user=self.request.user).order_by('id')
    
    def get(self, request, *args, **kwargs):
        cached = get_cached_response(request, prefix="tenants")
        if cached:
            logger.debug(f"Serving cached tenants for user={request.user}") 
            return Response(cached)
        
        response = super().get(request, *args, **kwargs)
        set_cached_response(request, response.data, prefix="tenants")
        logger.debug(f"Caching tenants for user={request.user}")
        return response

    def perform_create(self, serializer):
    #    return proper response on capacity validation error during tenant creation
        try:
            tenant = serializer.save(user=self.request.user)
            clear_cache_pattern(self.request, "tenants")
        except ValidationError as e:
            raise serializers.ValidationError({"detail": str(e)})

class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter to user's tenants, optionally by house_id"""
        queryset = Tenant.objects.filter(user=self.request.user)
        house_id = self.request.query_params.get('house_id')
        if house_id:
            queryset = queryset.filter(house_id=house_id)
            logger.debug(f"Filtered tenants by house_id={house_id} for user={self.request.user}")
        return queryset.order_by('id')


# ============================================================================
# HOUSE VIEWS
# ============================================================================

class HouseListView(generics.ListCreateAPIView):
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['house_number', 'house_size', 'house_rent_amount']

    def get_queryset(self):
        """Filter houses to only show current user's houses"""
        print("Fetching houses for user:", self.request.user)
        queryset = House.objects.filter(user=self.request.user)
        print("Initial queryset count:", queryset.count())
        
        # Optional filter by flat_building
        flat_building_id = self.request.query_params.get('flat_building_id')
        if flat_building_id:
            queryset = queryset.filter(flat_building_id=flat_building_id)
            logger.info(f"Filtering houses by flat_building_id={flat_building_id} for user={self.request.user}")
        
        return queryset.order_by('id')

    def get(self, request, *args, **kwargs):
        cached = get_cached_response(request, prefix="houses")
        if cached:
            logger.debug(f"Serving cached houses for user={request.user}")
            return Response(cached)
        response = super().get(request, *args, **kwargs)
        set_cached_response(request, response.data, prefix="houses")
        logger.debug(f"Caching houses for user={request.user}")
        return response
    


    def perform_create(self, serializer):
        """return proper response on capacity validation error during house creation"""
        try:
            house = serializer.save(user=self.request.user)
            clear_cache_pattern(self.request, "houses")
        except ValidationError as e:
            raise serializers.ValidationError({"detail": str(e)})

class HouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'
    
    def get_queryset(self):
        """Filter to user's houses only"""
        return House.objects.filter(user=self.request.user).order_by('id')


# ============================================================================
# FLAT BUILDING VIEWS
# ============================================================================

class FlatBuildingListView(generics.ListCreateAPIView):
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter flat buildings to current user, optionally by name"""
        queryset = FlatBuilding.objects.filter(user=self.request.user)
        
        # Optional search by name
        name = self.request.query_params.get('name')
        if name:
            # FIX: Changed from 'biulding_name' to 'building_name'
            queryset = queryset.filter(building_name__icontains=name)
        
        return queryset.order_by('id')

    def get(self, request, *args, **kwargs):
        cached = get_cached_response(request, prefix="flats")
        if cached:
            return Response(cached)
        response = super().get(request, *args, **kwargs)
        set_cached_response(request, response.data, prefix="flats")
        return response

    def perform_create(self, serializer):
        flat_building = serializer.save(user=self.request.user)
        clear_cache_pattern(self.request, "flats")


class FlatBuildingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk' 
    
    def get_queryset(self):
        """Filter to user's buildings only - no name search needed here"""
        return FlatBuilding.objects.filter(user=self.request.user).order_by('id')
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion if building has houses"""
        flat_building = self.get_object()
        if flat_building.houses.exists():
            return Response(
                {"message": "Cannot delete FlatBuilding with existing houses."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


# ============================================================================
# RENT PAYMENT VIEWS
# ============================================================================

class RentPaymentListView(generics.ListCreateAPIView):
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only show paid payments for current user"""
        return RentPayment.objects.filter(
            is_paid=True, 
            user=self.request.user
        ).order_by('id')

    def get(self, request, *args, **kwargs):
        cached = get_cached_response(request, prefix="rent_payments")
        if cached:
            return Response(cached)
        response = super().get(request, *args, **kwargs)
        set_cached_response(request, response.data, prefix="rent_payments")
        return response

    def perform_create(self, serializer):
        rent_payment = serializer.save(user=self.request.user)
        clear_cache_pattern(self.request, "rent_payments")


class RentPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RentPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter to user's payments, optionally by tenant"""
        queryset = RentPayment.objects.filter(user=self.request.user)
        
        tenant_id = self.request.query_params.get('tenant_id')
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset.order_by('id')


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

# @api_view(['POST'])
# @permission_classes([AllowAny])  # FIX: Changed from IsAuthenticated
# def admin_login(request):
#     """Login endpoint for admin users"""
#     logger.debug(f"Admin login attempt with data: {request.data}")
#     serializer = AdminLoginSerializer(data=request.data)
    
#     if serializer.is_valid():
#         username = serializer.validated_data['username']
#         password = serializer.validated_data['password']

#         logger.debug(f"Attempting to authenticate user: {username}")

#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             refresh = RefreshToken.for_user(user)
#             access_token = refresh.access_token

#             return Response({
#                 "message": "Login successful",
#                 "access_token": str(access_token),
#                 "refresh_token": str(refresh),
#             }, status=status.HTTP_200_OK)
#         else:
#             logger.debug(f"Authentication failed for user: {username}")
#             return Response({
#                 "message": "Invalid credentials or not a superuser",
#             }, status=status.HTTP_401_UNAUTHORIZED)
#     else:
#         logger.debug(f"Serializer errors: {serializer.errors}")
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

 
class RegisterAdminView(APIView):
    permission_classes = [permissions.AllowAny]

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
            RefreshToken(request.data['refresh_token']).blacklist()
            return Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
# ============================================================================
# LOGIN USER VIEW
# ============================================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def user_login(request):
    """Login endpoint for regular users"""
    logger.debug(f"User login attempt with data: {request.data}")
    logger.debug(request.data)
    print("DEBUG LOGIN BODY →", request.data)

    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(request, username=username, password=password)
    if user is not None:
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        return Response({
            "message": "Login successful",
            "access_token": str(access_token),
            "refresh_token": str(refresh),
        }, status=status.HTTP_200_OK)
    else:
        logger.debug(f"Authentication failed for user: {username}")
        return Response({
            "message": "Invalid credentials",
        }, status=status.HTTP_401_UNAUTHORIZED)
    
# ===========================================================================
# REGISTER USER VIEW
# ===========================================================================
# for normal user registration, not admin
class RegisterUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterAdminSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            email = serializer.validated_data.get('email', '')

            try:
                User.objects.create_user(username=username, password=password, email=email)
                return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)