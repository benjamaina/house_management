from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from decimal import Decimal
from datetime import datetime, timedelta
from django.core.cache import cache
from unittest.mock import patch
from tennants.models import Tenant, House, RentPayment, FlatBuilding



class BaseTestCase(APITestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        """Set up test users and authentication"""
        # CRITICAL: Clear cache before EACH test
        cache.clear()
        
        
        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123',
            email='user1@test.com'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123',
            email='user2@test.com'
        )
        
        # Create API clients
        self.client1 = APIClient()
        self.client2 = APIClient()
        
        # Authenticate clients
        self.client1.force_authenticate(user=self.user1)
        self.client2.force_authenticate(user=self.user2)
        
    def tearDown(self):
        """Clean up after each test"""
        cache.clear()


    def base_test_list_flat_buildings_filters_by_user(self):
        """Test that users only see their own flat buildings"""
        # User 1 creates a building
        FlatBuilding.objects.create(
            user=self.user1,
            building_name='User1 Building',
            address='Address 1',
            number_of_houses=5
        )
        
        # User 2 creates a building
        FlatBuilding.objects.create(
            user=self.user2,
            building_name='User2 Building',
            address='Address 2',
            number_of_houses=3
        )
        
        cache.clear()
        
        # User 1 should only see their building
        response = self.client1.get('/api/flats/')
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['building_name'], 'User1 Building')

        cache.clear()

        # User 2 should only see their building
        response = self.client2.get('/api/flats/')
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['building_name'], 'User2 Building')
   
    def base_test_filter_by_name(self):
        """Test filtering flat buildings by name"""
        FlatBuilding.objects.create(
            user=self.user1,
            building_name='Sunrise Apartments',
            address='Address 1',
            number_of_houses=5
        )
        FlatBuilding.objects.create(
            user=self.user1,
            building_name='Sunset Villa',
            address='Address 2',
            number_of_houses=3
        )
        
        cache.clear()
        response = self.client1.get('/api/flats/?name=Sunrise')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Sunrise', response.data['results'][0]['building_name'])
    
    def test_cache_works_correctly(self):
        """Test that caching returns same data on repeated requests"""
        FlatBuilding.objects.create(
            user=self.user1,
            building_name='Test Building',
            address='Address 1',
            number_of_houses=5
        )
        
        cache.clear()
        
        # First request - should hit database
        response1 = self.client1.get('/api/flats/')
        
        # Second request - should hit cache
        response2 = self.client1.get('/api/flats/')
        
        self.assertEqual(response1.data, response2.data)
    
    def test_cannot_delete_with_existing_houses(self):
        """Test that flat buildings with houses cannot be deleted"""
        flat = FlatBuilding.objects.create(
            user=self.user1,
            building_name='Test Building',
            address='Address 1',
            number_of_houses=5
        )
        
        house = House.objects.create(
            user=self.user1,
            flat_building=flat,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        
        response = self.client1.delete(f'/api/flats/{flat.pk}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot delete', response.data['message'])


class HouseViewTests(BaseTestCase):
    """Tests for House views"""
    
    def setUp(self):
        super().setUp()
        FlatBuilding.objects.all().delete()
        # Create flat buildings for both users
        self.flat1 = FlatBuilding.objects.create(
            user=self.user1,
            building_name='User1 Building',
            address='Address 1',
            number_of_houses=5
        )
        self.flat2 = FlatBuilding.objects.create(
            user=self.user2,
            building_name='User2 Building',
            address='Address 2',
            number_of_houses=3
        )
    
    def test_create_house(self):
        """Test creating a house"""
        data = {
            'flat_building': self.flat1.id,
            'house_number': '101',
            'house_size': '2 bedroom',
            'house_rent_amount': '1500.00',
            'deposit_amount': '3000.00'
        }
        
        response = self.client1.post('/api/houses/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        house = House.objects.first()
        self.assertEqual(house.user, self.user1)
        self.assertEqual(house.house_number, '101')
    
    def test_cannot_exceed_building_capacity(self):
        """Test that you can't create more houses than building capacity"""
        # Create flat with capacity of 2
        small_flat = FlatBuilding.objects.create(
            user=self.user1,
            building_name='Small Building',
            address='Address',
            number_of_houses=2
        )
        
        # Create first house - should succeed
        House.objects.create(
            user=self.user1,
            flat_building=small_flat,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        
        # Create second house - should succeed
        House.objects.create(
            user=self.user1,
            flat_building=small_flat,
            house_number='102',
            house_rent_amount=Decimal('1000.00')
        )
        
        # Try to create third house - should fail (model validation)
        data = {
            'flat_building': small_flat.id,
            'house_number': '103',
            'house_rent_amount': '1000.00'
        }
        
        response = self.client1.post('/api/houses/', data)
        # Model validation should prevent this
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_houses_filters_by_user(self):
        """Test that users only see their own houses"""
        # User 1 creates a house
        house1 = House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        
        # User 2 creates a house
        house2 = House.objects.create(
            user=self.user2,
            flat_building=self.flat2,
            house_number='201',
            house_rent_amount=Decimal('1500.00')
        )
        
        cache.clear()
        
        # User 1 should ONLY see their house
        response = self.client1.get('/api/houses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['house_number'], '101')
        

    def test_cannot_access_other_users_house_detail(self):
        """Test that users can't access other users' house details"""
        house = House.objects.create(
            user=self.user2,
            flat_building=self.flat2,
            house_number='201',
            house_rent_amount=Decimal('1500.00')
        )
        
        # User 1 tries to access User 2's house
        # Should get 404 because get_queryset filters it out
        response = self.client1.get(f'/api/houses/{house.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_filter_by_flat_building(self):
        """Test filtering houses by flat building"""
        House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='102',
            house_rent_amount=Decimal('1200.00')
        )
        
        cache.clear()
        response = self.client1.get(f'/api/houses/?flat_building_id={self.flat1.id}')
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)


class TenantViewTests(BaseTestCase):
    """Tests for Tenant views"""
    
    def setUp(self):
        super().setUp()
        self.flat1 = FlatBuilding.objects.create(
            user=self.user1,
            building_name='Test Building',
            address='Address 1',
            number_of_houses=5
        )
        self.house1 = House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        self.house2 = House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='102',
            house_rent_amount=Decimal('1000.00')
        )
    
    def test_create_tenant(self):
        """Test creating a tenant"""
        data = {
            'full_name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+254712345678',
            'id_number': '12345678',
            'house': self.house1.id
        }
        
        response = self.client1.post('/api/tennants/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        tenant = Tenant.objects.first()
        self.assertEqual(tenant.user, self.user1)
        self.assertEqual(tenant.full_name, 'John Doe')
    
    def test_cannot_add_tenant_to_full_house(self):
        """Test that house occupancy is enforced"""
        # Create first tenant
        tenant1 = Tenant.objects.create(
            user=self.user1,
            full_name='Tenant One',
            email='tenant1@example.com',
            phone='+254712345678',
            id_number='11111111',
            house=self.house1,
            is_active=True
        )
        
        # Try to create second tenant in same house - model should prevent this
        data = {
            'full_name': 'Tenant Two',
            'email': 'tenant2@example.com',
            'phone': '+254712345679',
            'id_number': '22222222',
            'house': self.house1.id
        }
        
        response = self.client1.post('/api/tennants/', data)
        # Model validation should prevent this
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('occupied', str(response.data).lower())
    
    def test_list_tenants_with_filters(self):
        """Test filtering tenants"""
        Tenant.objects.create(
            user=self.user1,
            full_name='Active Tenant',
            email='active@example.com',
            phone='+254712345678',
            id_number='11111111',
            house=self.house1,
            is_active=True
        )
        Tenant.objects.create(
            user=self.user1,
            full_name='Inactive Tenant',
            email='inactive@example.com',
            phone='+254712345679',
            id_number='22222222',
            house=self.house2,
            is_active=False
        )
        
        cache.clear()
        
        # Filter by active status
        response = self.client1.get('/api/tennants/?is_active=true')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['full_name'], 'Active Tenant')

class RentPaymentViewTests(BaseTestCase):
    """Tests for RentPayment views"""
    
    def setUp(self):
        super().setUp()
        self.flat1 = FlatBuilding.objects.create(
            user=self.user1,
            building_name='Test Building',
            address='Address 1',
            number_of_houses=5
        )
        self.house1 = House.objects.create(
            user=self.user1,
            flat_building=self.flat1,
            house_number='101',
            house_rent_amount=Decimal('1000.00')
        )
        self.tenant1 = Tenant.objects.create(
            user=self.user1,
            full_name='John Doe',
            email='john@example.com',
            phone='+254712345678',
            id_number='12345678',
            house=self.house1
        )
    
    def test_create_rent_payment(self):
        """Test creating a rent payment"""
        data = {
            'tenant': self.tenant1.id,
            'rent_month': 1,
            'year': 2024,
            'amount_paid': '1000.00',
            'payment_method': 'cash',
            'is_paid': True
        }
        
        response = self.client1.post('/api/rentpayments/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        payment = RentPayment.objects.first()
        self.assertEqual(payment.user, self.user1)
    
    def test_list_only_paid_payments(self):
        """Test that list view only shows paid payments"""
        # Create paid payment
        RentPayment.objects.create(
            user=self.user1,
            tenant=self.tenant1,
            rent_month=1,
            year=2024,
            amount_paid=Decimal('1000.00'),
            is_paid=True
        )
        
        # Create unpaid payment
        RentPayment.objects.create(
            user=self.user1,
            tenant=self.tenant1,
            rent_month=2,
            year=2024,
            amount_paid=Decimal('500.00'),
            is_paid=False
        )
        
        cache.clear()
        response = self.client1.get('/api/rentpayments/')
        # Should only return paid payments
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['rent_month'], 1)


class PermissionTests(BaseTestCase):
    """Tests for permission issues"""
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users can't access endpoints"""
        client = APIClient()  # No authentication
        
        response = client.get('/api/flats/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_isolation(self):
        """Test that users can't see each other's data"""
        # User 1 creates data
        flat1 = FlatBuilding.objects.create(
            user=self.user1,
            building_name='User1 Building',
            address='Address 1',
            number_of_houses=5
        )
        
        cache.clear()
        
        # User 2 shouldn't see User 1's data
        response = self.client2.get('/api/flats/')
        self.assertEqual(response.data['count'], 0)


class AuthenticationTests(TestCase):
    """Tests for login/logout functionality"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='userpass123',
            email='user@test.com'
        )
    
    def test_admin_login_success(self):
        """Test admin can login"""
        data = {
            'username': 'admin',
            'password': 'adminpass123'
        }
        
        response = self.client.post('/api/admin/login/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
    
    def test_regular_user_cannot_admin_login(self):
        """Test that regular users can't use admin login"""
        data = {
            'username': 'regular',
            'password': 'userpass123'
        }
        
        response = self.client.post('/api/admin/login/', data)
        # Regular user should be denied (but authenticated, so serializer validation catches it)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])
    
    def test_register_admin(self):
        """Test admin registration"""
        data = {
            'username': 'newadmin',
            'password': 'newpass123',
            'email': 'newadmin@test.com'
        }
        
        response = self.client.post('/api/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify user was created
        user = User.objects.get(username='newadmin')
        self.assertTrue(user.is_superuser)


# Summary comment for running tests:
# python manage.py test tennants.tests.test_tenant_views --verbosity=2
# python manage.py test tennants.tests.test_tenant_views.HouseViewTests --verbosity=2