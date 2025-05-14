### 🏠 **House Management System**

A full-stack house management system with:

* A **custom React frontend** (generated via AI and manually integrated)
* A **Django REST Framework (DRF) backend** providing APIs
* **JWT authentication** (SimpleJWT)
* **Redis caching** for performance
* Mpesa integration (partial)
* Admin-focused features with plans for user support

---

### 🚀 Features

* **Tenant, House, and Rent Payment management** via APIs
* **JWT-based Authentication** (login/logout/refresh)
* **Custom Frontend UI** built using React + Tailwind (RippleUI)
* **Django backend** built with DRF, integrated with Redis
* **Partially integrated Mpesa API** (payment simulation & notifications)
* Admin and user account registration via API
* Token-protected endpoints
* Fully decoupled architecture

---

### 📁 Tech Stack

* **Frontend:** React + RippleUI + Fetch API
* **Backend:** Django, Django REST Framework
* **Authentication:** JWT (SimpleJWT)
* **Cache:** Redis
* **Payments:** Mpesa (Safaricom API)
* **Database:** SQLite (can upgrade to PostgreSQL/MySQL)

---

### 🧪 API Endpoints (Sample)

* `POST /api/token/` — obtain JWT token
* `GET /api/tenants/` — list tenants
* `POST /api/payments/` — create payment
* `GET /api/houses/` — list houses
* `POST /api/register/` — register a user

(You can link to a full Postman collection or docs if available)

---

### ⚙️ Setup Instructions

1. **Backend Setup**

   ```bash
   cd backend/
   python -m venv web-venv
   source web-venv/bin/activate  # or Scripts\activate on Windows
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```

2. **Frontend Setup**

   ```bash
   cd frontend/
   npm install
   npm run dev
   ```

3. **Redis (optional but recommended)**

   * Make sure Redis is running on default port 6379

---

### 📌 Notes

* This project was built solo over \~4 months.
* It began as a learning project without a clear plan and evolved into a full-stack system.
* The frontend was AI-assisted but manually integrated with the backend.
* Optimization and Mpesa integration are in progress.

---

### 🔒 TODO / Future Plans

* Full Mpesa integration
* Admin dashboard UI improvements
* Switch to PostgreSQL
* Containerization (Docker)
* Unit and integration testing

