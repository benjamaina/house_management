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
    <meta name="description" content="A simple system for landlords and caretakers to track houses, tenants, rent payments, and balances in one place.">
    <title>RentTrack - Manage Tenants, Rent & Payments Simply</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary-blue: #3b82f6;
            --accent-yellow: #dcf11c;
            --accent-green: #39e416;
            --dark-bg: #0a0a0f;
            --dark-card: #111118;
            --dark-border: #1e1e2a;
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--dark-bg);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 0 24px;
        }

        /* Navigation */
        nav {
            padding: 20px 0;
            border-bottom: 1px solid var(--dark-border);
        }

        .nav-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent-yellow) 0%, var(--accent-green) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .logo-icon svg {
            width: 24px;
            height: 24px;
            fill: #000;
        }

        .logo-text {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .nav-link {
            color: var(--text-primary);
            text-decoration: none;
            font-weight: 500;
            padding: 10px 24px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--dark-border);
            transition: all 0.2s ease;
        }

        .nav-link:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        /* Hero Section */
        .hero {
            padding: 80px 0 60px;
            text-align: center;
        }

        .hero h1 {
            font-size: 2.8rem;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 20px;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
        }

        .hero h1 .highlight {
            color: var(--accent-yellow);
        }

        .hero-subtitle {
            font-size: 1.15rem;
            color: var(--text-secondary);
            max-width: 550px;
            margin: 0 auto 40px;
        }

        .btn-primary {
            display: inline-block;
            padding: 16px 40px;
            font-size: 1.05rem;
            font-weight: 600;
            text-decoration: none;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--accent-yellow) 0%, var(--accent-green) 100%);
            color: #000;
            box-shadow: 0 8px 30px rgba(220, 241, 28, 0.25);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(220, 241, 28, 0.35);
        }

        /* Pain Points Section */
        .pain-section {
            padding: 60px 0;
        }

        .section-label {
            text-align: center;
            font-size: 0.85rem;
            color: var(--accent-yellow);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 16px;
            font-weight: 600;
        }

        .section-title {
            text-align: center;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 40px;
        }

        .pain-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
        }

        .pain-card {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 16px;
            padding: 28px;
        }

        .pain-icon {
            width: 48px;
            height: 48px;
            background: rgba(239, 68, 68, 0.15);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
        }

        .pain-icon svg {
            width: 24px;
            height: 24px;
            stroke: #ef4444;
        }

        .pain-card h3 {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .pain-card p {
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        /* Solutions Section */
        .solutions-section {
            padding: 60px 0;
        }

        .solution-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
        }

        .solution-card {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 16px;
            padding: 28px;
        }

        .solution-icon {
            width: 48px;
            height: 48px;
            background: rgba(57, 228, 22, 0.15);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
        }

        .solution-icon svg {
            width: 24px;
            height: 24px;
            stroke: var(--accent-green);
        }

        .solution-card h3 {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .solution-card p {
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        /* Dashboard Preview */
        .preview-section {
            padding: 60px 0;
            text-align: center;
        }

        .dashboard-preview {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 20px;
            padding: 24px;
            margin-top: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }

        .preview-header {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }

        .preview-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--dark-border);
        }

        .preview-dot.red { background: #ef4444; }
        .preview-dot.yellow { background: #eab308; }
        .preview-dot.green { background: #22c55e; }

        .preview-content {
            background: var(--dark-bg);
            border-radius: 12px;
            padding: 30px;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }

        .stat-card {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 12px;
            padding: 20px;
            text-align: left;
        }

        .stat-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .stat-value.green { color: var(--accent-green); }
        .stat-value.yellow { color: var(--accent-yellow); }
        .stat-value.red { color: #ef4444; }

        /* How It Works */
        .steps-section {
            padding: 60px 0;
        }

        .steps-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }

        .step-card {
            text-align: center;
            padding: 30px;
        }

        .step-number {
            width: 56px;
            height: 56px;
            background: linear-gradient(135deg, var(--accent-yellow) 0%, var(--accent-green) 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
            font-weight: 700;
            color: #000;
            margin: 0 auto 20px;
        }

        .step-card h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .step-card p {
            font-size: 0.9rem;
            color: var(--text-muted);
        }

        /* Audience Section */
        .audience-section {
            padding: 60px 0;
        }

        .audience-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-top: 40px;
        }

        .audience-card {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 16px;
            padding: 32px;
        }

        .audience-card h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .audience-card h3.perfect { color: var(--accent-green); }
        .audience-card h3.not-ideal { color: var(--text-muted); }

        .audience-list {
            list-style: none;
        }

        .audience-list li {
            padding: 10px 0;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.95rem;
        }

        .audience-list li svg {
            width: 18px;
            height: 18px;
            flex-shrink: 0;
        }

        .audience-list li svg.check { stroke: var(--accent-green); }
        .audience-list li svg.x { stroke: var(--text-muted); }

        /* Trust Section */
        .trust-section {
            padding: 60px 0;
            text-align: center;
        }

        .trust-badges {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 16px;
            margin-top: 30px;
        }

        .trust-badge {
            background: var(--dark-card);
            border: 1px solid var(--dark-border);
            border-radius: 50px;
            padding: 12px 24px;
            font-size: 0.9rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .trust-badge svg {
            width: 18px;
            height: 18px;
            stroke: var(--accent-green);
        }

        /* CTA Section */
        .cta-section {
            padding: 80px 0;
            text-align: center;
        }

        .cta-box {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(57, 228, 22, 0.1) 100%);
            border: 1px solid var(--dark-border);
            border-radius: 24px;
            padding: 60px 40px;
        }

        .cta-box h2 {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 16px;
        }

        .cta-box p {
            color: var(--text-secondary);
            margin-bottom: 30px;
            font-size: 1.05rem;
        }

        /* Footer */
        footer {
            padding: 30px 0;
            border-top: 1px solid var(--dark-border);
            text-align: center;
        }

        footer p {
            color: var(--text-muted);
            font-size: 0.85rem;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .hero h1 {
                font-size: 2rem;
            }

            .preview-content {
                grid-template-columns: 1fr;
            }

            .section-title {
                font-size: 1.5rem;
            }

            .cta-box {
                padding: 40px 24px;
            }

            .cta-box h2 {
                font-size: 1.6rem;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav>
        <div class="container nav-content">
            <a href="/" class="logo">
                <div class="logo-icon">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    </svg>
                </div>
                <span class="logo-text">RentTrack</span>
            </a>
            <a href="login/" class="nav-link">Login</a>
        </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero">
        <div class="container">
            <h1>Manage tenants, rent, and payments — <span class="highlight">without spreadsheets or WhatsApp chaos.</span></h1>
            <p class="hero-subtitle">A simple system for landlords and caretakers to track houses, tenants, rent payments, and balances in one place.</p>
            <a href="register/" class="btn-primary">Get Started Free</a>
        </div>
    </section>

    <!-- Pain Points -->
    <section class="pain-section">
        <div class="container">
            <p class="section-label">Sound familiar?</p>
            <h2 class="section-title">The rent tracking headaches you know too well</h2>
            <div class="pain-grid">
                <div class="pain-card">
                    <div class="pain-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                        </svg>
                    </div>
                    <h3>Forgetting who paid rent</h3>
                    <p>Losing track of which tenants have paid and which haven't this month.</p>
                </div>
                <div class="pain-card">
                    <div class="pain-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
                        </svg>
                    </div>
                    <h3>Scrolling M-Pesa messages</h3>
                    <p>Digging through SMS history to confirm if a payment actually came through.</p>
                </div>
                <div class="pain-card">
                    <div class="pain-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                        </svg>
                    </div>
                    <h3>Records that get lost</h3>
                    <p>Paper notes and spreadsheets that become outdated or disappear entirely.</p>
                </div>
                <div class="pain-card">
                    <div class="pain-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
                        </svg>
                    </div>
                    <h3>No clear rent balances</h3>
                    <p>Can't tell at a glance how much each tenant owes or has overpaid.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Solutions -->
    <section class="solutions-section">
        <div class="container">
            <p class="section-label">The solution</p>
            <h2 class="section-title">Everything you need to manage rent properly</h2>
            <div class="solution-grid">
                <div class="solution-card">
                    <div class="solution-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                    </div>
                    <h3>Rent status at a glance</h3>
                    <p>See instantly who has paid, who's pending, and who's overdue.</p>
                </div>
                <div class="solution-card">
                    <div class="solution-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
                        </svg>
                    </div>
                    <h3>All payment types tracked</h3>
                    <p>M-Pesa, cash, bank transfers — everything in one system.</p>
                </div>
                <div class="solution-card">
                    <div class="solution-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 15.75V18m-7.5-6.75h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V13.5zm0 2.25h.008v.008H8.25v-.008zm0 2.25h.008v.008H8.25V18zm2.498-6.75h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V13.5zm0 2.25h.007v.008h-.007v-.008zm0 2.25h.007v.008h-.007V18zm2.504-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zm0 2.25h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V18zm2.498-6.75h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V13.5zM8.25 6h7.5v2.25h-7.5V6zM12 2.25c-1.892 0-3.758.11-5.593.322C5.307 2.7 4.5 3.65 4.5 4.757V19.5a2.25 2.25 0 002.25 2.25h10.5a2.25 2.25 0 002.25-2.25V4.757c0-1.108-.806-2.057-1.907-2.185A48.507 48.507 0 0012 2.25z" />
                        </svg>
                    </div>
                    <h3>Automatic balances</h3>
                    <p>Balances update automatically with every recorded payment.</p>
                </div>
                <div class="solution-card">
                    <div class="solution-icon">
                        <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
                        </svg>
                    </div>
                    <h3>One dashboard for all</h3>
                    <p>Manage houses, units, and tenants from a single place.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Dashboard Preview -->
    <section class="preview-section">
        <div class="container">
            <p class="section-label">See it in action</p>
            <h2 class="section-title">A clean dashboard that makes sense</h2>
            <div class="dashboard-preview">
                <div class="preview-header">
                    <span class="preview-dot red"></span>
                    <span class="preview-dot yellow"></span>
                    <span class="preview-dot green"></span>
                </div>
                <div class="preview-content">
                    <div class="stat-card">
                        <p class="stat-label">Total Units</p>
                        <p class="stat-value">24</p>
                    </div>
                    <div class="stat-card">
                        <p class="stat-label">Paid This Month</p>
                        <p class="stat-value green">18</p>
                    </div>
                    <div class="stat-card">
                        <p class="stat-label">Overdue</p>
                        <p class="stat-value red">3</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- How It Works -->
    <section class="steps-section">
        <div class="container">
            <p class="section-label">How it works</p>
            <h2 class="section-title">Get started in 3 simple steps</h2>
            <div class="steps-grid">
                <div class="step-card">
                    <div class="step-number">1</div>
                    <h3>Add your houses & units</h3>
                    <p>Register your buildings and the individual units you manage.</p>
                </div>
                <div class="step-card">
                    <div class="step-number">2</div>
                    <h3>Register tenants</h3>
                    <p>Add tenants with their rent amounts and move-in dates.</p>
                </div>
                <div class="step-card">
                    <div class="step-number">3</div>
                    <h3>Record & track payments</h3>
                    <p>Log payments and see balances update instantly.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Audience -->
    <section class="audience-section">
        <div class="container">
            <p class="section-label">Who is this for?</p>
            <h2 class="section-title">Built for small-scale property managers</h2>
            <div class="audience-grid">
                <div class="audience-card">
                    <h3 class="perfect">
                        <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Perfect for
                    </h3>
                    <ul class="audience-list">
                        <li>
                            <svg class="check" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Landlords with 1–50 units
                        </li>
                        <li>
                            <svg class="check" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Caretakers managing rentals for owners
                        </li>
                        <li>
                            <svg class="check" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                            Small property managers
                        </li>
                    </ul>
                </div>
                <div class="audience-card">
                    <h3 class="not-ideal">
                        <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Not ideal for
                    </h3>
                    <ul class="audience-list">
                        <li>
                            <svg class="x" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Large real-estate companies
                        </li>
                        <li>
                            <svg class="x" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Those needing custom ERP systems
                        </li>
                        <li>
                            <svg class="x" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            Commercial property management
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </section>

    <!-- Trust Signals -->
    <section class="trust-section">
        <div class="container">
            <p class="section-label">Why trust us?</p>
            <h2 class="section-title">Built with landlords in mind</h2>
            <div class="trust-badges">
                <div class="trust-badge">
                    <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                    </svg>
                    Secure authentication
                </div>
                <div class="trust-badge">
                    <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Role-based access
                </div>
                <div class="trust-badge">
                    <svg fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
                    </svg>
                    Built from real pain points
                </div>
            </div>
        </div>
    </section>

    <!-- Final CTA -->
    <section class="cta-section">
        <div class="container">
            <div class="cta-box">
                <h2>Start managing rent the smart way</h2>
                <p>Join landlords who've said goodbye to spreadsheet chaos.</p>
                <a href="register/" class="btn-primary">Create Free Account</a>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer>
        <div class="container">
            <p>© 2024 RentTrack. Built for landlords, by developers who get it.</p>
        </div>
    </footer>
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
