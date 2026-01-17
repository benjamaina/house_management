from django.urls import path
from .views import (PaymentDetailView, TenantListView,HouseDetailView,TenantDetailView, 
                    FlatBuildingDetailView, user_login, AdminLogoutView, HouseListView,FlatBuildingListView, PaymentListView, 
                    RegisterAdminView, RegisterUserView,
                    BuildingListView, BuildingCreateView, BuildingDetailView, BuildingUpdateView, BuildingDeleteView,
                    HouseCreateView, HouseListView , HouseUpdateView, HouseDeleteView, HouseDetailView, dashboard,
                    TenantCreateView, TenantUpdateView, TenantDeleteView, TenantDetailView,
                    PaymentListView, PaymentCreateView, RentChargeListView, RentChargeDetailView,RentChargeCreateView, RentChargeUpdateView, bulk_create_rent_charges
)

urlpatterns = [
    path('tennants/', TenantListView.as_view(), name = 'tennant-list'),
    path('tennants/<int:pk>/', TenantDetailView.as_view(),name ='tennants-list'),

    path("houses/", HouseListView.as_view(), name="house-list"),
    path('houses/<int:pk>/', HouseDetailView.as_view(), name = 'house-detail'),
    path('admin/logout/', AdminLogoutView.as_view(), name='admin_logout'),
    path('user/login/', user_login, name='admin_login'),
    
    path("flats/", FlatBuildingListView.as_view(), name="flat-list"),
    path('flats/new/', FlatBuildingDetailView.as_view(), name='flat-update'),
    path('flats/<int:pk>/', FlatBuildingDetailView.as_view(), name='flat-detail'),
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('register/user/', RegisterUserView.as_view(), name='register-user'),

    
]


urlpatterns = [
    # ========================================
    # WEB INTERFACE (Template-based)
    # ========================================
    path('', dashboard, name='dashboard'),
    
    # Buildings
    path('buildings/', BuildingListView.as_view(), name='building_list'),
    path('buildings/add/', BuildingCreateView.as_view(), name='building_add'),
    path('buildings/<int:pk>/', BuildingDetailView.as_view(), name='building_detail'),
    path('buildings/<int:pk>/edit/', BuildingUpdateView.as_view(), name='building_edit'),
    path('buildings/<int:pk>/delete/', BuildingDeleteView.as_view(), name='building_delete'),
    
    # Houses
    path('houses/', HouseListView.as_view(), name='house_list'),
    path('houses/add/', HouseCreateView.as_view(), name='house_add'),
    path('houses/<int:pk>/', HouseDetailView.as_view(), name='house_detail'),
    path('houses/<int:pk>/edit/', HouseUpdateView.as_view(), name='house_edit'),
    path('houses/<int:pk>/delete/', HouseDeleteView.as_view(), name='house_delete'),

    # Tenants
    path('tenants/', TenantListView.as_view(), name='tenant_list'),
    path('tenants/add/', TenantCreateView.as_view(), name='tenant_add'),
    path('tenants/<int:pk>/', TenantDetailView.as_view(), name='tenant_detail'),
    path('tenants/<int:pk>/edit/', TenantUpdateView.as_view(), name='tenant_edit'),
    path('tenants/<int:pk>/delete/', TenantDeleteView.as_view(), name='tenant_delete'), 

    # Payments
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('payments/add/', PaymentCreateView.as_view(), name='payment_add'),
    path('payments/<int:pk>/', PaymentListView.as_view(), name='payment_detail'),
    path('payments/<int:pk>/edit/', PaymentDetailView.as_view(), name='payment_edit'),

    # Rent Charges
    path('rent-charges/', RentChargeListView.as_view(), name='rent_charge_list'),
    path('rent-charges/add/', RentChargeCreateView.as_view(), name='rent_charge_add'),
    path('rent-charges/<int:pk>/', RentChargeDetailView.as_view(), name='rent_charge_detail'),
    path('rent-charges/<int:pk>/edit/', RentChargeUpdateView.as_view(), name='rent_charge_edit'),
    path('rent-charges/bulk-create/', bulk_create_rent_charges, name='rent_charge_bulk_create'),


]