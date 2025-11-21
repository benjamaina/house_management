from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.core.cache import cache
from tennants.models import FlatBuilding, House, Tenant, RentPayment


class TenantModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpass123'
        )
        self.flat_building = FlatBuilding.objects.create(
            user=self.user,
            building_name="Test Building",
            address="123 Test Street",
            number_of_houses=5
        )
        self.house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="101",
            house_rent_amount=1000.00,
            deposit_amount=500.00
        )
        self.tenant = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john.doe@example.com",
            phone="+254712345678",
            id_number="1234567890",
            house=self.house,
            is_active=True,
            balance=0
        )

    def test_tenant_creation(self):
        """Test basic Tenant creation"""
        self.assertEqual(self.tenant.full_name, "John Doe")
        self.assertEqual(self.tenant.email, "john.doe@example.com")
        self.assertEqual(self.tenant.phone, "+254712345678")
        self.assertEqual(self.tenant.id_number, "1234567890")
        self.assertTrue(self.tenant.is_active)
        self.assertEqual(str(self.tenant), "John Doe")

    def test_tenant_properties(self):
        """Test computed properties of Tenant"""
        self.assertEqual(self.tenant.building_name, "Test Building")
        self.assertEqual(self.tenant.building_adress, "123 Test Street")
        self.assertEqual(self.tenant.rent, 1000.00)
        self.assertEqual(self.tenant.security_deposit, 500.00)

    def test_tenant_validation_rules(self):
        """Test Tenant validation rules"""
        # Test duplicate email
        tenant2 = Tenant(
            user=self.user,
            full_name="Jane Doe",
            email="john.doe@example.com",  # Same email
            phone="+254712345679",
            house=self.house,
            id_number="87654321"
        )
        with self.assertRaises(ValidationError):
            tenant2.full_clean()

        # Test duplicate phone
        tenant2 = Tenant(
            user=self.user,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+254712345678",  # Same phone
            house=self.house,
            id_number="87654321"
        )
        with self.assertRaises(ValidationError):
            tenant2.full_clean()

    def test_multiple_tenants_same_house_validation(self):
        """Test that only one active tenant can occupy a house"""
        # Try to create another active tenant in the same house
        tenant2 = Tenant(
            user=self.user,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+254712345679",
            house=self.house,
            is_active=True,
            id_number="87654321"
        )
        
        with self.assertRaises(ValidationError):
            tenant2.full_clean()

    def test_update_balance_method(self):
        """Test update_balance method"""
        # Create rent payments
        rent_payment1 = RentPayment.objects.create(
            user=self.user,
            tenant=self.tenant,
            rent_month=1,
            year=2024,
            rent_amount=1000,
            amount_paid=500,
            is_paid=False
        )
        
        rent_payment2 = RentPayment.objects.create(
            user=self.user,
            tenant=self.tenant,
            rent_month=2,
            year=2024,
            rent_amount=1000,
            amount_paid=300,
            is_paid=False
        )
        
        # Update balance
        new_balance = self.tenant.update_balance()
        
        # Calculate expected balance: (1000-500) + (1000-300) = 500 + 700 = 1200
        expected_balance = (1000 - 500) + (1000 - 300)
        self.assertEqual(new_balance, expected_balance)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.balance, expected_balance)

    def test_cache_invalidation_on_tenant_save(self):
        """Test that tenant cache is invalidated on save"""
        # Set cache
        cache_key = f"tenant:{self.tenant.id}"
        cache.set(cache_key, "cached_data", timeout=60)
        
        # Verify cache is set
        self.assertIsNotNone(cache.get(cache_key))
        
        # Save tenant - should clear cache via signal
        self.tenant.full_name = "Updated Name"
        self.tenant.save()
        
        # Cache should be cleared by signal
        self.assertIsNone(cache.get(cache_key))

    def test_cache_invalidation_on_tenant_delete(self):
        """Test that tenant cache is invalidated on delete"""
        # Create a tenant to delete

        other_house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="102",
            house_rent_amount=1100.00,
            deposit_amount=550.00
        )
        tenant_to_delete = Tenant.objects.create(
            user=self.user,
            full_name="Temp Tenant",
            email="temp@example.com",
            phone="+254712345679",
            house=other_house,
            id_number="99887766",
            is_active=False
        )
        
        # Set cache
        cache_key = f"tenant:{tenant_to_delete.id}"
        cache.set(cache_key, "cached_data", timeout=60)
        
        # Verify cache is set
        self.assertIsNotNone(cache.get(cache_key))
        
        # Delete tenant - should clear cache via signal
        tenant_to_delete.delete()
        
        # Cache should be cleared by signal
        self.assertIsNone(cache.get(cache_key))

    def test_house_occupation_signal_on_tenant_save(self):
        """Test that house occupation is updated via signal on tenant save"""
        # Create a new house for testing
        test_house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="102",
            house_rent_amount=1200
        )
        
        # House should initially not be occupied
        self.assertFalse(test_house.occupation)
        
        # Create active tenant - should trigger signal
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="New Tenant",
            email="new@example.com",
            phone="+254712345674",
            house=test_house,
            is_active=True,
            id_number="9988776655"  
        )
        
        # House should now be occupied via signal
        test_house.refresh_from_db()
        self.assertTrue(test_house.occupation)
        
        # Deactivate tenant
        tenant.is_active = False
        tenant.save()
        
        # House should no longer be occupied via signal
        test_house.refresh_from_db()
        self.assertFalse(test_house.occupation)

    def test_house_occupation_signal_on_tenant_delete(self):
        """Test that house occupation is updated via signal on tenant delete"""
        # Create a tenant in a house
        test_house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="103",
            house_rent_amount=1300
        )
        
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="Delete Test Tenant",
            email="delete@example.com",
            phone="+254712345675",
            house=test_house,
            is_active=True,
            id_number="5566778899"
        )
        
        # Verify house is occupied
        test_house.refresh_from_db()
        self.assertTrue(test_house.occupation)
        
        # Delete tenant - should trigger signal
        tenant.delete()
        
        # House should no longer be occupied via signal
        test_house.refresh_from_db()
        self.assertFalse(test_house.occupation)

    def test_building_cache_invalidation_on_tenant_operations(self):
        """Test that building cache is invalidated on tenant operations"""
        # Set building cache
        cache.set(f"flat_{self.flat_building.pk}_occupied", 0, timeout=60)
        cache.set(f"flat_{self.flat_building.pk}_vacant", 5, timeout=60)
        # create a new house in the building
        new_house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="104",
            house_rent_amount=1400
        )
        # Create tenant - this should trigger house save which clears building cache
        new_tenant = Tenant.objects.create(
            user=self.user,
            full_name="Cache Test Tenant",
            email="cache@example.com",
            phone="+254712345676",
            house=new_house,
            is_active=True,
            id_number="1122334455"
        )
        
        # Building cache should be cleared via house signals
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))

    def test_string_representation(self):
        """Test string representation of Tenant"""
        self.assertEqual(str(self.tenant), "John Doe")
        # create a new house
        new_house = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="105",
            house_rent_amount=1500
        )
        tenant2 = Tenant.objects.create(
            user=self.user,
            full_name="Jane Smith",
            email="jane@example.com",
            phone="+254712345679",
            id_number="0987654321",
            house=new_house,
            is_active=True
        )
        self.assertEqual(str(tenant2), "Jane Smith")