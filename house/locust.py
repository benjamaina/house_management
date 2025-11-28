from locust import HttpUser, task, between, SequentialTaskSet
import json
import random
from datetime import datetime

class AuthenticatedTaskSet(SequentialTaskSet):
    """Base task set that handles JWT authentication"""
    
    def on_start(self):
        """Called when a simulated user starts - handles login and token storage"""
        # Try to login with existing user or register a new one
        username = f"testuser_{random.randint(1000, 9999)}"
        password = "TestPass123!"
        email = f"{username}@example.com"

        
        # First, try to register
        with self.client.post(
            "/api/register/",
            json={
                "username": username,
                "password": password,
                "email": email,
                "first_name": "Test",
                "last_name": "User"
            },
            catch_response=True
        ) as register_response:
            # If registration fails (user exists), that's okay
            if register_response.status_code not in [201, 400]:
                register_response.failure(f"Unexpected registration status: {register_response.status_code}")
            else:
                register_response.success()
        
        # Now login to get tokens
        with self.client.post(
            "/api/admin/login/",
            json={
                "username": username,
                "password": password
            },
            catch_response=True
        ) as login_response:
            if login_response.status_code == 200:
                data = login_response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                if not self.access_token:
                    login_response.failure("No access token in response")
                else:
                    login_response.success()
            else:
                login_response.failure(f"Login failed with status {login_response.status_code}")
                self.access_token = None
                self.refresh_token = None
    
    def get_auth_headers(self):
        """Return headers with JWT authentication"""
        if self.access_token:
            return {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        return {"Content-Type": "application/json"}
    
    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False
        
        with self.client.post(
            "/api/token/refresh/",
            json={"refresh": self.refresh_token},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access")
                response.success()
                return True
            else:
                response.failure(f"Token refresh failed: {response.status_code}")
                return False


class RentalManagementTasks(AuthenticatedTaskSet):
    """Main task set for testing rental management endpoints"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.flat_building_ids = []
        self.house_ids = []
        self.vacant_house_ids = []  # Track houses without tenants
        self.tenant_ids = []
        self.rent_payment_ids = []
        self.tenant_rent_months = {}  # Track which months have been paid per tenant
    
    @task(2)
    def test_home_page(self):
        """Test the home page endpoint"""
        self.client.get("/", name="Home Page")
    
    @task(5)
    def test_create_flat_building(self):
        """Create a new flat building"""
        building_data = {
            "building_name": f"Building_{random.randint(1, 10000)}_{datetime.now().timestamp()}",
            "address": f"{random.randint(1, 999)} Main Street",
            "number_of_houses": random.randint(10, 30)  # Increased to allow more houses
        }
        
        with self.client.post(
            "/api/flats/",
            json=building_data,
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Create Flat Building"
        ) as response:
            if response.status_code == 201:
                building_id = response.json().get("id")
                self.flat_building_ids.append(building_id)
                response.success()
            elif response.status_code == 401:
                # Token might be expired, try to refresh
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
                else:
                    response.failure("Authentication failed")
            else:
                response.failure(f"Failed with status {response.status_code}")
    
    @task(10)
    def test_list_flat_buildings(self):
        """List all flat buildings"""
        with self.client.get(
            "/api/flats/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="List Flat Buildings"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
                else:
                    response.failure("Authentication failed")
    
    @task(3)
    def test_get_flat_building_detail(self):
        """Get details of a specific flat building"""
        if not self.flat_building_ids:
            return
        
        building_id = random.choice(self.flat_building_ids)
        
        with self.client.get(
            f"/api/flats/{building_id}/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Get Flat Building Detail"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Flat building not found")
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(4)
    def test_create_house(self):
        """Create a new house"""
        if not self.flat_building_ids:
            # Need a building first
            return
        
        building_id = random.choice(self.flat_building_ids)
        
        # House number must be max 5 characters
        house_number = str(random.randint(100, 999))
        
        house_data = {
            "flat_building": building_id,
            "house_number": house_number,
            "house_size": random.choice(["1 bedroom", "2 bedroom", "3 bedroom", "studio"]),
            "house_rent_amount": random.randint(5000, 30000),
            "deposit_amount": random.randint(5000, 30000),
            "occupation": False
        }
        
        with self.client.post(
            "/api/houses/",
            json=house_data,
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Create House"
        ) as response:
            if response.status_code == 201:
                house_id = response.json().get("id")
                self.house_ids.append(house_id)
                self.vacant_house_ids.append(house_id)  # New house is vacant
                response.success()
            elif response.status_code == 400:
                response.failure(f"Validation error: {response.text}")
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(8)
    def test_list_houses(self):
        """List all houses"""
        with self.client.get(
            "/api/houses/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="List Houses"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(6)
    def test_list_houses_by_building(self):
        """List houses filtered by flat building"""
        if not self.flat_building_ids:
            return
        
        building_id = random.choice(self.flat_building_ids)
        
        with self.client.get(
            f"/api/houses/?flat_building_id={building_id}",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="List Houses by Building"
        ) as response:
            if response.status_code == 200:
                response.success()
    
    @task(3)
    def test_create_tenant(self):
        """Create a new tenant - only assign to vacant houses"""
        if not self.vacant_house_ids:
            # No vacant houses available
            return
        
        # Pick a vacant house and remove it from the list
        house_id = self.vacant_house_ids.pop(0)
        
        # Generate unique identifiers
        unique_id = f"{random.randint(10000, 99999)}"
        timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds for more uniqueness
        
        tenant_data = {
            "full_name": f"Tenant_{unique_id}",
            "email": f"tenant{timestamp}@example.com",
            "phone": f"+254{random.randint(700000000, 799999999)}",
            "id_number": f"{timestamp % 100000000}",  # Keep it 8 digits
            "house": house_id,
            "is_active": True,
            "balance": 0,
            "rent_due_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        with self.client.post(
            "/api/tennants/",
            json=tenant_data,
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Create Tenant"
        ) as response:
            if response.status_code == 201:
                tenant_id = response.json().get("id")
                self.tenant_ids.append(tenant_id)
                self.tenant_rent_months[tenant_id] = set()  # Track paid months
                response.success()
            elif response.status_code == 400:
                # If failed, put the house back in vacant list
                self.vacant_house_ids.append(house_id)
                response.failure(f"Validation error: {response.text}")
            elif response.status_code == 401:
                self.vacant_house_ids.append(house_id)
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(10)
    def test_list_tenants(self):
        """List all tenants"""
        with self.client.get(
            "/api/tennants/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="List Tenants"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(4)
    def test_get_tenant_detail(self):
        """Get details of a specific tenant"""
        if not self.tenant_ids:
            return
        
        tenant_id = random.choice(self.tenant_ids)
        
        with self.client.get(
            f"/api/tennants/{tenant_id}/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Get Tenant Detail"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Tenant not found")
    
    @task(2)
    def test_create_rent_payment(self):
        """Create a rent payment - avoid duplicate month/year combinations"""
        if not self.tenant_ids:
            return
        
        tenant_id = random.choice(self.tenant_ids)
        
        # Get months that haven't been paid yet for this tenant
        current_year = datetime.now().year
        paid_months = self.tenant_rent_months.get(tenant_id, set())
        
        # Find an unpaid month
        available_months = [m for m in range(1, 13) if (current_year, m) not in paid_months]
        
        if not available_months:
            # All months paid for this year, skip
            return
        
        rent_month = random.choice(available_months)
        
        payment_data = {
            "tenant": tenant_id,
            "rent_month": rent_month,
            "year": current_year,
            "amount_paid": random.randint(5000, 30000),
            "payment_method": random.choice(["cash", "mobile_money", "bank_transfer"]),
            "is_paid": True
        }
        
        with self.client.post(
            "/api/rentpayments/",
            json=payment_data,
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Create Rent Payment"
        ) as response:
            if response.status_code == 201:
                rent_payment_id = response.json().get("id")
                self.rent_payment_ids.append(rent_payment_id)
                # Mark this month as paid
                self.tenant_rent_months[tenant_id].add((current_year, rent_month))
                response.success()
            elif response.status_code == 400:
                response.failure(f"Validation error: {response.text}")
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(7)
    def test_list_rent_payments(self):
        """List all rent payments"""
        with self.client.get(
            "/api/rentpayments/",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="List Rent Payments"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                if self.refresh_access_token():
                    response.failure("Token expired - refreshed")
    
    @task(2)
    def test_filter_tenants_by_active(self):
        """Filter tenants by active status"""
        with self.client.get(
            "/api/tennants/?is_active=true",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Filter Active Tenants"
        ) as response:
            if response.status_code == 200:
                response.success()
    
    @task(2)
    def test_search_flat_building_by_name(self):
        """Search flat buildings by name"""
        with self.client.get(
            "/api/flats/?name=Building",
            headers=self.get_auth_headers(),
            catch_response=True,
            name="Search Flat Buildings"
        ) as response:
            if response.status_code == 200:
                response.success()


class WebsiteUser(HttpUser):
    """Simulated user for load testing"""
    tasks = [RentalManagementTasks]
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = "http://localhost:8000"  # Change to your actual host
    
    # You can also set these via command line: 
    # locust -f locust.py --host=http://your-domain.com


class QuickTestUser(HttpUser):
    """Quick test user with shorter wait times for rapid testing"""
    tasks = [RentalManagementTasks]
    wait_time = between(0.5, 1.5)
    host = "http://localhost:8000"


class HeavyLoadUser(HttpUser):
    """Heavy load user for stress testing"""
    tasks = [RentalManagementTasks]
    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"