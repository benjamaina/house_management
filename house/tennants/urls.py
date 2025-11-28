from django.urls import path
from .views import (TenantListView,HouseDetailView,TenantDetailView, 
                    FlatBuildingDetailView, user_login, AdminLogoutView, HouseListView,FlatBuildingListView, RentPaymentListView, 
                    RegisterAdminView, RegisterUserView) 

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
    path('rentpayments/', RentPaymentListView.as_view(), name='rent-payment-list'),
    path('register/user/', RegisterUserView.as_view(), name='register-user'),

    
]
