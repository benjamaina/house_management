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
from tennants.views import RegistrationForm


def home(request):
# print a html and a login admin link
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>House Management System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #000000 0%, #1e3a8a 50%, #1d4ed8 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            text-align: center;
            max-width: 700px;
            width: 100%;
        }

        .logo {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #dcf11c 0%, #39e416 100%);
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 30px;
            box-shadow: 0 15px 40px rgba(220, 241, 28, 0.3);
        }

        .logo svg {
            width: 50px;
            height: 50px;
            fill: #000000;
        }

        h1 {
            font-size: 2.8rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 15px;
            line-height: 1.2;
        }

        .highlight {
            color: #dcf11c;
        }

        .subtitle {
            font-size: 1.1rem;
            color: #93c5fd;
            margin-bottom: 40px;
            line-height: 1.6;
        }

        .buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-block;
            padding: 16px 32px;
            font-size: 1rem;
            font-weight: 600;
            text-decoration: none;
            border-radius: 12px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .btn:hover {
            transform: translateY(-3px);
        }

        .btn-primary {
            background: linear-gradient(135deg, #dcf11c 0%, #39e416 100%);
            color: #000000;
            box-shadow: 0 8px 30px rgba(220, 241, 28, 0.4);
        }

        .btn-primary:hover {
            box-shadow: 0 12px 40px rgba(220, 241, 28, 0.5);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .footer {
            margin-top: 60px;
            color: #60a5fa;
            font-size: 0.85rem;
        }

        @media (max-width: 600px) {
            h1 {
                font-size: 2rem;
            }
            .buttons {
                flex-direction: column;
                align-items: center;
            }
            .btn {
                width: 100%;
                max-width: 250px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <svg viewBox="0 0 24 24">
                <path d="M12 3L4 9v12h5v-7h6v7h5V9l-8-6z"/>
            </svg>
        </div>
        
        <h1>Welcome to <span class="highlight">House Management</span></h1>
        <p class="subtitle">Streamline your property management with our powerful and intuitive system.</p>
        
        <div class="buttons">
            <a href="/login/" class="btn btn-primary">Admin Dashboard</a>
            <a href="/register/" class="btn btn-secondary">Register</a>
        </div>

        <p class="footer">© 2024 House Management System</p>
    </div>
</body>
</html>

    """
    return HttpResponse(html)
     
urlpatterns = [
    path("", home, name="home"),
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
