from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.cache import cache
from tennants.models import FlatBuilding, House, Tenant


class FlatBuildingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpass123'
        )
        self.flat_building = FlatBuilding.objects.create(
            user=self.user,
            building_name="Test Building",
            address="123 Test Street",
            number_of_houses=10
        )

    def test_flat_building_creation(self):
        """Test basic FlatBuilding creation"""
        self.assertEqual(self.flat_building.building_name, "Test Building")
        self.assertEqual(self.flat_building.address, "123 Test Street")
        self.assertEqual(self.flat_building.number_of_houses, 10)
        self.assertEqual(str(self.flat_building), "Test Building")

    def test_flat_building_validation(self):
        """Test FlatBuilding validation rules"""
        # Test negative number of houses
        building = FlatBuilding(
            user=self.user,
            building_name="Invalid Building",
            address="Test Address",
            number_of_houses=-1
        )
        with self.assertRaises(ValidationError):
            building.full_clean()

        # Test missing building name
        building = FlatBuilding(
            user=self.user,
            building_name="",
            address="Test Address",
            number_of_houses=5
        )
        with self.assertRaises(ValidationError):
            building.full_clean()

    def test_occupied_count_property_initial_state(self):
        """Test how_many_occupied property - initial state"""
        # Initially no houses should be occupied
        cache.clear()  # Ensure cache is clear
        self.assertEqual(self.flat_building.how_many_occupied, 0)

    def test_occupied_count_after_house_creation(self):
        """Test how_many_occupied after creating occupied house"""
        # Create occupied house - signals will update cache
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Refresh from database and test - should reflect the new occupied house
        self.flat_building.refresh_from_db()
        self.assertEqual(self.flat_building.how_many_occupied, 1)

    def test_vacant_houses_property_initial_state(self):
        """Test vacant_houses property - initial state"""
        # Initially all houses should be vacant
        cache.clear()  # Ensure cache is clear
        self.assertEqual(self.flat_building.vacant_houses, 10)

    def test_vacant_houses_after_house_creation(self):
        """Test vacant_houses after creating occupied house"""
        # Create occupied house
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Refresh and test - should reflect one less vacant house
        self.flat_building.refresh_from_db()
        self.assertEqual(self.flat_building.vacant_houses, 9)

    def test_get_occupied_count_with_cache_miss(self):
        """Test occupied count caching functionality - cache miss scenario"""
        # Clear cache to ensure fresh start
        cache.clear()
        
        # Initial count should be 0 (no houses created yet)
        self.assertEqual(self.flat_building.get_occupied_count(), 0)

    def test_get_occupied_count_with_cache_hit(self):
        """Test occupied count caching functionality - cache hit scenario"""
        # Clear cache
        cache.clear()
        
        # Initial call should populate cache
        initial_count = self.flat_building.get_occupied_count()
        self.assertEqual(initial_count, 0)
        
        # Create occupied house (this should clear cache via signal)
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Subsequent call should recalculate due to cache clear by signal
        new_count = self.flat_building.get_occupied_count()
        self.assertEqual(new_count, 1)

    def test_get_vacant_count_with_cache(self):
        """Test vacant count caching functionality"""
        # Clear cache
        cache.clear()
        
        # Initial count should be 10
        self.assertEqual(self.flat_building.get_vacant_count(), 10)
        
        # Create occupied house (should clear cache via signal)
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Should recalculate due to cache clear by signal
        self.assertEqual(self.flat_building.get_vacant_count(), 9)

    def test_cache_clear_on_house_operations(self):
        """Test that cache is properly cleared on house operations"""
        # Set initial cache values
        cache.set(f"flat_{self.flat_building.pk}_occupied", 5, timeout=60)
        cache.set(f"flat_{self.flat_building.pk}_vacant", 5, timeout=60)
        
        # Verify cache is set
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNotNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))
        
        # Create house - should clear cache via signal
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Cache should be cleared by signal
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_occupied"))
        self.assertIsNone(cache.get(f"flat_{self.flat_building.pk}_vacant"))
        
        # Now get_occupied_count should recalculate fresh
        self.assertEqual(self.flat_building.get_occupied_count(), 1)

    def test_tenant_count_method(self):
        """Test tenant_count method"""
        # Create house and tenant
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        tenant = Tenant.objects.create(
            user=self.user,
            full_name="John Doe",
            email="john@example.com",
            phone="+254712345678",
            house=house,
            is_active=True,
            id_number="12345678"
        )
        
        self.assertEqual(self.flat_building.tenant_count(), 1)

    def test_delete_flat_building_with_occupied_houses(self):
        """Test deletion prevention for buildings with occupied houses"""
        # Create occupied house
        house = House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=True
        )
        
        # Try to delete building with occupied houses
        with self.assertRaises(ValidationError):
            self.flat_building.delete()

    def test_successful_delete_flat_building(self):
        """Test successful deletion of building without occupied houses"""
        # Create vacant house
        House.objects.create(
            flat_building=self.flat_building,
            house_number="101",
            occupation=False
        )
        
        # Should be able to delete
        self.flat_building.delete()
        self.assertEqual(FlatBuilding.objects.count(), 0)

    def test_string_representation(self):
        """Test the string representation of FlatBuilding"""
        self.assertEqual(str(self.flat_building), "Test Building")
        
        building2 = FlatBuilding.objects.create(
            user=self.user,
            building_name="Another Building",
            address="456 Other Street",
            number_of_houses=5
        )
        self.assertEqual(str(building2), "Another Building")

    def test_mixed_occupied_vacant_houses(self):
        """Test counting with mixed occupied and vacant houses"""
        # Create some occupied and some vacant houses
        House.objects.create(flat_building=self.flat_building, house_number="101", occupation=True)
        House.objects.create(flat_building=self.flat_building, house_number="102", occupation=False)
        House.objects.create(flat_building=self.flat_building, house_number="103", occupation=True)
        House.objects.create(flat_building=self.flat_building, house_number="104", occupation=False)
        
        # Refresh and verify counts
        self.flat_building.refresh_from_db()
        self.assertEqual(self.flat_building.how_many_occupied, 2)
        self.assertEqual(self.flat_building.vacant_houses, 8)  # 10 total - 2 occupied