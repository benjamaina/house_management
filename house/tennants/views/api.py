import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, serializers, status
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from tennants.models import FlatBuilding, House, Payment, RentCharge, Tenant
from tennants.serializers import (
    FlatBuildingSerializer, HouseSerializer, PaymentSerializer,
    RentChargeSerializer, TenantSerializer,
)
from django.db.models import ProtectedError



logger = logging.getLogger(__name__)


class ProtectedDeleteConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "This record has financial history and can't be deleted. "
        "Deactivate it instead."
    )
    default_code = "protected_delete"


class ApiViewMixin:
    cache_prefix = None

    def handle_exception(self, exc):
        if isinstance(exc, ProtectedError):
            exc = ProtectedDeleteConflict()
        elif isinstance(exc, DjangoValidationError):
            exc = serializers.ValidationError({"detail": exc.messages})

        return super().handle_exception(exc)

    def _bust(self):
        if self.cache_prefix:
            clear_cache_pattern(self.request, self.cache_prefix)

    def list(self, request, *args, **kwargs):
        if self.cache_prefix:
            cached = get_cached_response(request, self.cache_prefix)
            if cached is not None:
                return Response(cached)

        response = super().list(request, *args, **kwargs)

        if self.cache_prefix:
            set_cached_response(request, response.data, self.cache_prefix)

        return response

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        self._bust()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._bust()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._bust()




CACHE_TTL = getattr(settings, "CACHE_TTL", 60 * 5)


# ============================================================================
# CACHE HELPERS: per-user, per-prefix version counter.
# Bumping the counter makes every old key unreachable, which works on LocMem and Redis.
# ============================================================================

def _user_id(request):
    return getattr(request.user, "id", "anon")


def _version_key(request, prefix):
    return f"ver:{prefix}:{_user_id(request)}"


def make_cache_key(request, prefix=""):
    version = cache.get(_version_key(request, prefix), 1)
    raw = f"{prefix}:{version}:{_user_id(request)}:{request.get_full_path()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_cached_response(request, prefix=""):
    return cache.get(make_cache_key(request, prefix))


def set_cached_response(request, data, prefix=""):
    cache.set(make_cache_key(request, prefix), data, CACHE_TTL)


def clear_cache_pattern(request, prefix):
    key = _version_key(request, prefix)
    try:
        cache.incr(key)
    except ValueError:               # key doesn't exist yet
        cache.set(key, 2, None)


class ApiViewMixin:
    """
    - turns Django ValidationError into a 400 (on create, update AND delete)
    - caches list responses and invalidates on create/update/delete
    """
    cache_prefix = None

    def handle_exception(self, exc):
        if isinstance(exc, ProtectedError):
            exc = serializers.ValidationError(
                {"detail": "This record has financial history and can't be deleted. Deactivate it instead."}
            )
        elif isinstance(exc, DjangoValidationError):
            exc = serializers.ValidationError({"detail": exc.messages})
        return super().handle_exception(exc)

    def _bust(self):
        if self.cache_prefix:
            clear_cache_pattern(self.request, self.cache_prefix)

    def list(self, request, *args, **kwargs):
        if self.cache_prefix:
            cached = get_cached_response(request, self.cache_prefix)
            if cached is not None:
                return Response(cached)
        response = super().list(request, *args, **kwargs)
        if self.cache_prefix:
            set_cached_response(request, response.data, self.cache_prefix)
        return response

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        self._bust()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._bust()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._bust()


# ============================================================================
# TENANTS
# ============================================================================

class TenantListView(ApiViewMixin, generics.ListCreateAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["is_active", "house", "full_name"]
    ordering_fields = ["full_name", "created_at"]
    cache_prefix = "tenants"

    def get_queryset(self):
        return (Tenant.objects.filter(user=self.request.user)
                .select_related("house__flat_building").order_by("id"))


class TenantDetailView(ApiViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "tenants"

    def get_queryset(self):
        queryset = (Tenant.objects.filter(user=self.request.user)
                    .select_related("house__flat_building"))
        house_id = self.request.query_params.get("house_id")
        if house_id:
            queryset = queryset.filter(house_id=house_id)
        return queryset.order_by("id")


# ============================================================================
# HOUSES
# ============================================================================

class HouseListView(ApiViewMixin, generics.ListCreateAPIView):
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]          # ordering_fields did nothing without this
    ordering_fields = ["house_number", "house_size", "house_rent_amount"]
    cache_prefix = "houses"

    def get_queryset(self):
        queryset = House.objects.filter(user=self.request.user).select_related("flat_building")
        flat_building_id = self.request.query_params.get("flat_building_id")
        if flat_building_id:
            queryset = queryset.filter(flat_building_id=flat_building_id)
        return queryset.order_by("id")


class HouseDetailView(ApiViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HouseSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "houses"

    def get_queryset(self):
        return (House.objects.filter(user=self.request.user)
                .select_related("flat_building").order_by("id"))


# ============================================================================
# FLAT BUILDINGS
# ============================================================================

class FlatBuildingListView(ApiViewMixin, generics.ListCreateAPIView):
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "flats"

    def get_queryset(self):
        queryset = FlatBuilding.objects.filter(user=self.request.user)
        name = self.request.query_params.get("name")
        if name:
            queryset = queryset.filter(building_name__icontains=name)
        return queryset.order_by("id")


class FlatBuildingDetailView(ApiViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FlatBuildingSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "flats"

    def get_queryset(self):
        return FlatBuilding.objects.filter(user=self.request.user).order_by("id")

    def destroy(self, request, *args, **kwargs):
        if self.get_object().houses.exists():
            return Response({"message": "Cannot delete FlatBuilding with existing houses."},
                            status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


# ============================================================================
# PAYMENTS
# ============================================================================

class PaymentListView(ApiViewMixin, generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "rent_payments"

    def get_queryset(self):
        return (Payment.objects.filter(user=self.request.user)
                .select_related("tenant", "rent_charge").order_by("id"))


class PaymentDetailView(ApiViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "rent_payments"

    def get_queryset(self):
        queryset = (Payment.objects.filter(user=self.request.user)
                    .select_related("tenant", "rent_charge"))
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by("id")


# ============================================================================
# RENT CHARGES (the previously duplicated, PaymentSerializer-backed views)
# ============================================================================

class RentChargeListView(ApiViewMixin, generics.ListCreateAPIView):
    serializer_class = RentChargeSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "rent_charges"

    def get_queryset(self):
        return (RentCharge.objects.filter(user=self.request.user)
                .select_related("tenant").order_by("id"))


class RentChargeDetailView(ApiViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RentChargeSerializer
    permission_classes = [IsAuthenticated]
    cache_prefix = "rent_charges"

    def get_queryset(self):
        queryset = RentCharge.objects.filter(user=self.request.user).select_related("tenant")
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        return queryset.order_by("id")