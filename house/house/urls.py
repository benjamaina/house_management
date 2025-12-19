"""
URL configuration for house project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework.authtoken.views import obtain_auth_token
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt import views as jwt_views
from tennants import views
from tennants.views import RegistrationForm, landing_page


     
urlpatterns = [
    path("", landing_page, name="landing"),
    path("admin/", admin.site.urls),
    path("api/admin/logout/", TokenRefreshView.as_view(), name="admin_logout"),
    path("acounts/", include("django.contrib.auth.urls")),
    path("api/", include("tennants.urls")),
    path("api/token/",jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name='login.html'), name="login"),
    path("dashboard/", login_required(views.dashboard), name="dashboard"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),    
]
