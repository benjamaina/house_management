from locust import HttpUser, task, between, SequentialTaskSet
import random
from datetime import datetime


class AuthenticatedTaskSet(SequentialTaskSet):
    def on_start(self):
        username = f"testuser_{random.randint(1000, 9999)}"
        password = "TestPass123!"
        email = f"{username}@example.com"

        # Register
        self.client.post(
            "/api/api/register/",
            json={
                "username": username,
                "password": password,
                "email": email,
                "first_name": "Test",
                "last_name": "User"
            }
        )

        # Login
        response = self.client.post(
            "/api/api/login/",
            json={
                "username": username,
                "password": password
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
        else:
            self.access_token = None

    def get_auth_headers(self):
        if self.access_token:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        return {"Content-Type": "application/json"}


class RentalManagementTasks(AuthenticatedTaskSet):

    def __init__(self, parent):
        super().__init__(parent)
        self.flat_building_ids = []
        self.house_ids = []
        self.vacant_house_ids = []
        self.tenant_ids = []
        self.rent_charge_ids = {}   # ✅ tenant_id -> [charges]
        self.rent_payment_ids = []

    # ------------------------------
    # Buildings
    # ------------------------------
    @task(5)
    def create_flat(self):
        data = {
            "building_name": f"Building_{random.randint(1,10000)}",
            "address": "Test Address",
            "number_of_houses": random.randint(5, 20)
        }

        res = self.client.post(
            "/api/api/flats/",
            json=data,
            headers=self.get_auth_headers()
        )

        if res.status_code == 201:
            self.flat_building_ids.append(res.json()["id"])

    @task(5)
    def list_flats(self):
        self.client.get("/api/api/flats/", headers=self.get_auth_headers())

    # ------------------------------
    # Houses
    # ------------------------------
    @task(5)
    def create_house(self):
        if not self.flat_building_ids:
            return

        data = {
            "flat_building": random.choice(self.flat_building_ids),
            "house_number": str(random.randint(100, 999)),
            "house_size": "2 bedroom",
            "house_rent_amount": random.randint(5000, 20000),
            "deposit_amount": random.randint(5000, 20000),
            "occupation": False
        }

        res = self.client.post(
            "/api/api/houses/",
            json=data,
            headers=self.get_auth_headers()
        )

        if res.status_code == 201:
            house_id = res.json()["id"]
            self.house_ids.append(house_id)
            self.vacant_house_ids.append(house_id)

    # ------------------------------
    # Tenants
    # ------------------------------
    @task(5)
    def create_tenant(self):
        if not self.vacant_house_ids:
            return

        house_id = self.vacant_house_ids.pop(0)

        data = {
            "full_name": f"Tenant_{random.randint(1000,9999)}",
            "email": f"tenant{random.randint(10000,99999)}@test.com",
            "phone": f"+2547{random.randint(10000000,99999999)}",
            "id_number": str(random.randint(10000000,99999999)),
            "house": house_id,
            "is_active": True,
            "rent_due_date": datetime.now().strftime("%Y-%m-%d")
        }

        res = self.client.post(
            "/api/api/tenants/",
            json=data,
            headers=self.get_auth_headers()
        )

        if res.status_code == 201:
            tenant_id = res.json()["id"]
            self.tenant_ids.append(tenant_id)

    # ------------------------------
    # Rent Charges ✅ NEW
    # ------------------------------
    @task(4)
    def create_rent_charge(self):
        if not self.tenant_ids:
            return

        tenant_id = random.choice(self.tenant_ids)

        month = random.randint(1, 12)

        data = {
            "tenant": tenant_id,
            "year": datetime.now().year,
            "month": month,
            "amount_due": random.randint(5000, 20000)
        }

        res = self.client.post(
            "/api/api/rentcharges/",
            json=data,
            headers=self.get_auth_headers()
        )

        if res.status_code == 201:
            charge_id = res.json()["id"]

            if tenant_id not in self.rent_charge_ids:
                self.rent_charge_ids[tenant_id] = []

            self.rent_charge_ids[tenant_id].append(charge_id)

    # ------------------------------
    # Payments ✅ FIXED
    # ------------------------------
    @task(4)
    def create_payment(self):
        if not self.rent_charge_ids:
            return

        tenant_id = random.choice(list(self.rent_charge_ids.keys()))
        charges = self.rent_charge_ids.get(tenant_id, [])

        if not charges:
            return

        data = {
            "tenant": tenant_id,
            "rent_charge": random.choice(charges),
            "amount": random.randint(5000, 20000),
            "payment_method": "cash"
        }

        res = self.client.post(
            "/api/api/payments/",
            json=data,
            headers=self.get_auth_headers()
        )

        if res.status_code == 201:
            self.rent_payment_ids.append(res.json()["id"])
        elif res.status_code == 400:
            print("🔥 PAYMENT ERROR:", res.text)

    @task(5)
    def list_payments(self):
        self.client.get("/api/api/payments/", headers=self.get_auth_headers())


class WebsiteUser(HttpUser):
    tasks = [RentalManagementTasks]
    wait_time = between(1, 3)
    host = "http://localhost:8000"