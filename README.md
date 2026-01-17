🏠 House Management System — Technical Highlights

A hybrid Django application for managing rental properties, tenants, and rent records, showcasing backend development, relational data handling, and performance optimization.

🎯 Purpose

Demonstrates real-world backend development skills:

Relational data modeling

CRUD operations via API and HTML views

Performance optimization and testing

Designed to showcase clear thinking and problem-solving for technical reviewers.

🧱 Architecture Overview

Backend Framework: Django + Django REST Framework

Database: MySQL (relational models)

Caching: Django cache framework (Redis compatible)

Authentication: Django Auth + JWT (SimpleJWT)

Views:

HTML (server-rendered, class/function-based views)

JSON REST API (CRUD endpoints)

Testing & Performance:

Unit testing with Django’s test framework
🔐 Authentication (JWT)
Stress testing with Locust

Pagination for large datasets

Efficient relational fetching with select_related

⚡ Key Features (Technical)

Relational Data Handling:

Houses, Buildings, Tenants, RentPayments

select_related for optimized joins

Demonstrates relational thinking without raw SQL

API & Web Interface:

Full CRUD operations via REST API (JSON)

Server-rendered HTML pages for admin/user actions

Performance & Scalability:

Caching to reduce database load

Pagination for large tables

Optional request throttling

Locust stress testing

Authentication & Security:

Session-based authentication for web

JWT for API endpoints

Scoped access per user

Testing & Quality:

Unit tests covering core models and API endpoints

Documentation and usage examples

🔗 Application Structure

Web (HTML)

/ — Landing page

/login/, /logout/, /register/

/dashboard/

CRUD pages for Buildings, Houses, Tenants, Payments

API (JSON)

/api/tenants/, /api/houses/, /api/flat-buildings/, /api/rent-payments/

/api/token/, /api/token/refresh/

Fully authenticated endpoints

🛠️ How to Run Locally
git clone https://github.com/benjamaina/house-management.git
cd house-management
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

📌 Project Status

Actively developed, backend-focused

Designed for small to medium property management

Emphasis on readable architecture and technical clarity
