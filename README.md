# 🏠 House Management System

A full-featured backend system built with Django REST Framework for managing rental properties, tenants, and rent payments — complete with JWT authentication, M-Pesa payment integration, and Redis caching for performance.

## 🚀 Features

- ✅ Secure JWT-based authentication using SimpleJWT
- 🏢 CRUD operations for Houses, Tenants, and Flat Buildings
- 💸 M-Pesa STK Push payment integration
- 📥 Payment notification handling
- ⚡ Redis caching for optimized performance
- 🔐 Admin login/logout functionality
- 📦 Fully decoupled API for frontend integration

## 🛠️ Tech Stack

- **Backend Framework:** Django 4+ / Django REST Framework
- **Auth:** JWT (SimpleJWT)
- **Database:** SQLite (configurable)
- **Payments:** M-Pesa Daraja API
- **Caching:** Redis
- **Deployment-ready:** Production-optimized structure

## 🔧 API Endpoints

### Authentication
- `POST /api/token/` — Get access/refresh token  
- `POST /api/token/refresh/` — Refresh token  
- `POST /admin-login/` — Admin login  
- `POST /admin-logout/` — Admin logout  

### Tenants
- `GET /api/tenants/`
- `POST /api/tenants/`
- `GET /api/tenants/<id>/`
- `PUT /api/tenants/<id>/`
- `DELETE /api/tenants/<id>/`

### Houses / Flats / Rent
- `GET /api/houses/`, `POST /api/houses/`, etc.
- `GET /api/flat-buildings/` (includes Redis caching)
- `GET /api/rent-payments/` and full CRUD support

### Payments
- `POST /initiate-stk/` — Initiate payment via M-Pesa  
- `POST /payment-notification/` — Receive payment callback  

## 🧪 Running the Project Locally

```bash
# Clone the repo
git clone https://github.com/benjamaina/house-management.git
cd house-management

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver
