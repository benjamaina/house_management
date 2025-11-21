from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache
from tennants.models import FlatBuilding, House, Tenant


class HouseModelTest(TestCase):
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
            house_size="1 bedroom",
            house_rent_amount=1000.00,
            deposit_amount=500.00,
            occupation=False
        )

    def test_house_creation(self):
        """Test basic House creation"""
        self.assertEqual(self.house.house_number, "101")
        self.assertEqual(self.house.house_rent_amount, 1000.00)
        self.assertEqual(self.house.deposit_amount, 500.00)
        self.assertFalse(self.house.occupation)
        self.assertEqual(str(self.house), "Test Building - House 101")

    def test_unique_house_per_building_constraint(self):
        """Test unique house number constraint per building"""
        duplicate_house = House(
            user=self.user,
            flat_building=self.flat_building,
            house_number="101",  # Same house number
            house_size="1 bedroom"
        )
        
        with self.assertRaises(ValidationError):
            duplicate_house.full_clean()

    def test_house_validation_rules(self):
        """Test various House validation rules"""
        # Test negative rent amount
        house = House(
            flat_building=self.flat_building,
            house_number="102",
            house_rent_amount=-100,
            deposit_amount=500
        )
        with self.assertRaises(ValidationError):
            house.full_clean()

        # Test negative deposit amount
        house = House(
            flat_building=self.flat_building,
            house_number="102",
            house_rent_amount=1000,
            deposit_amount=-500
        )
        with self.assertRaises(ValidationError):
            house.full_clean()

    def test_house_number_uniqueness_in_same_building(self):
        """Test that house numbers must be unique within the same building"""
        # Create another building
        another_building = FlatBuilding.objects.create(
            user=self.user,
            building_name="Another Building",
            address="456 Other Street",
            number_of_houses=5
        )
        
        # Same house number in different building should be allowed
        house2 = House(
            flat_building=another_building,
            house_number="101",  # Same number, different building
            house_rent_amount=1200
        )
        
        try:
            house2.full_clean()  # Should not raise ValidationError
            house2.save()
        except ValidationError:
            self.fail("Same house number in different buildings should be allowed")

    def test_auto_change_occupation_method(self):
        """Test auto_change_occupation method"""
        # Initially not occupied
        self.assertFalse(self.house.occupation)
        
        # Create active tenant
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john@example.com",
            phone="+254712345678",
            house=self.house,
            is_active=True,
            id_number="A12345678"
        )
        
        # Call auto_change_occupation
        self.house.auto_change_occupation()
        self.house.refresh_from_db()
        
        # Should now be occupied
        self.assertTrue(self.house.occupation)

    def test_auto_change_occupation_with_inactive_tenant(self):
        """Test auto_change_occupation with inactive tenant"""
        # Create inactive tenant
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john@example.com",
            phone="+254712345678",
            house=self.house,
            is_active=False,
            id_number="A12345678"
        )
        
        # Call auto_change_occupation
        self.house.auto_change_occupation()
        self.house.refresh_from_db()
        
        # Should not be occupied since tenant is inactive
        self.assertFalse(self.house.occupation)

    def test_delete_occupied_house(self):
        """Test prevention of deleting occupied houses"""
        # Create tenant and mark house as occupied
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john@example.com",
            phone="+254712345678",
            house=self.house,
            is_active=True,
            id_number="A12345678"
        )
        self.house.occupation = True
        self.house.save()
        
        # Try to delete occupied house
        with self.assertRaises(ValidationError):
            self.house.delete()

    # def test_house_count_validation(self):
    #     """Test that house count doesn't exceed building capacity"""
    #     # Fill up all houses
    #     for i in range(5):
    #         House.objects.create(
    #             flat_building=self.flat_building,
    #             house_number=f"10{i+2}",
    #             house_rent_amount=1000
    #         )
        
    #     # Try to create one more house
    #     extra_house = House(
    #         flat_building=self.flat_building,
    #         house_number="106",
    #         house_rent_amount=1000
    #     )
        
    #     with self.assertRaises(ValidationError):
    #         extra_house.full_clean()

    def test_multiple_active_tenants_validation(self):
        """Test validation for multiple active tenants in one house"""
        # Create first active tenant
        tenant1 = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john@example.com",
            phone="+254712345678",
            house=self.house,
            is_active=True,
            id_number="A12345678"
        )
        
        # Try to create second active tenant in same house
        tenant2 = Tenant(
            user=self.user,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+254712345679",
            house=self.house,
            is_active=True,
            id_number="B87654321"
        )
        
        with self.assertRaises(ValidationError):
            tenant2.full_clean()

    def test_cache_invalidation_on_house_save(self):
        """Test that building cache is invalidated when house is saved"""
        # Set cache values
        cache.set(f"flat_{self.flat_building.pk}_occupied", 2, timeout=60)
        cache.set(f"flat_{self.flat_building.pk}_vacant", 3, timeout=60)
        
        # Verify cache is set
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))
        
        # Save house - should clear cache via signal
        self.house.house_rent_amount = 1200
        self.house.save()
        
        # Cache should be cleared by signal
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))

    def test_cache_invalidation_on_house_delete(self):
        """Test that building cache is invalidated when house is deleted"""
        # Create a house to delete
        house_to_delete = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="102",
            house_rent_amount=1000
        )
        
        # Set cache values
        cache.set(f"flat_{self.flat_building.pk}_occupied", 1, timeout=60)
        cache.set(f"flat_{self.flat_building.pk}_vacant", 4, timeout=60)
        
        # Verify cache is set
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))
        
        # Delete house - should clear cache via signal
        house_to_delete.delete()
        
        # Cache should be cleared by signal
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))

    def test_occupation_auto_update_via_tenant_signals(self):
        """Test that house occupation is automatically updated via tenant signals"""
        # Initially not occupied
        self.assertFalse(self.house.occupation)
        
        # Create active tenant - should trigger signal to update occupation
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="Test Tenant",
            email="test@example.com",
            phone="+254712345678",
            house=self.house,
            is_active=True,
            id_number="T12345678"
        )
        
        # House should now be occupied via signal
        self.house.refresh_from_db()
        self.assertTrue(self.house.occupation)
        
        # Deactivate tenant - should trigger signal to update occupation
        tenant.is_active = False
        tenant.save()
        
        # House should no longer be occupied via signal
        self.house.refresh_from_db()
        self.assertFalse(self.house.occupation)

    def test_string_representation(self):
        """Test string representation includes both building and house number"""
        self.assertEqual(str(self.house), "Test Building - House 101")
        
        house2 = House.objects.create(
            user=self.user,
            flat_building=self.flat_building,
            house_number="202",
            house_rent_amount=1200
        )
        self.assertEqual(str(house2), "Test Building - House 202")