🏠 House Management System

A hybrid Django application for managing rental properties, tenants, and rent records.

The system provides:

REST API endpoints (JSON) for programmatic access and future integrations

Server-rendered web views (HTML) for landlords/caretakers to manage data directly in the browser

The project focuses on data management and tracking, not payment processing.

🎯 Purpose

Designed for landlords and caretakers who want:

Clear visibility of tenants and occupancy

Accurate rent and payment records

A simple, self-hosted management system

The application records payments but does not integrate directly with financial institutions.

🧱 Architecture Overview

Hybrid view layer

Django REST Framework views for JSON APIs

Django class-based and function-based views for HTML pages

Shared domain models

Houses, Buildings, Tenants, Rent Payments

Single authentication system

Django Auth + JWT (SimpleJWT)

🚀 Features

🔐 Authentication (session-based + JWT)

🏢 Manage buildings, houses, and occupancy

👥 Tenant lifecycle management (active/inactive)

💰 Rent and payment tracking

📊 Dashboard with summary statistics

⚡ Optional caching using Django’s cache framework

🧑‍💼 Django Admin for system-level administration

🛠️ Tech Stack

Framework: Django, Django REST Framework

Authentication: Django Auth, JWT (SimpleJWT)

Database: MySQL

Caching: Django cache framework (Redis when available)

Frontend: Server-rendered Django templates

🔗 Application Structure
Web (HTML)

/ — Landing page

/login/, /logout/, /register/

/dashboard/

CRUD pages for buildings, houses, tenants, and payments

API (JSON)

/api/tenants/

/api/houses/

/api/flat-buildings/

/api/rent-payments/

/api/token/, /api/token/refresh/

All API endpoints are authenticated and scoped to the logged-in user.

🚫 Out of Scope (by design)

No direct M-Pesa or bank integrations

No multi-tenant SaaS billing

No frontend framework (React/Next.js)

🧪 Running Locally
git clone https://github.com/benjamaina/house-management.git
cd house-management

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

📌 Project Status

Actively developed

Backend-focused

Intended for small to medium property management use

Architecture kept explicit and readable over compactness