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
# from tennants.views import RegisterAdminView


def home(request):
    return HttpResponse("Welcome to the home page!")
     
urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/admin/logout/", TokenRefreshView.as_view(), name="admin_logout"),
    # path("api/register", RegisterAdminView.as_view(), name='register'),
    path("acounts/", include("django.contrib.auth.urls")),
    path("api/", include("tennants.urls")),
    path("api/token/",jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),

]
