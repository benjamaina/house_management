from django.test import TestCase
from django.core.cache import cache
from tennants.models import FlatBuilding

class FlatBuildingCacheTest(TestCase):
    def setUp(self):
        self.flat = FlatBuilding.objects.create(name="Test Flats", address="123 Street", number_of_houses=10)

    def test_cache_storage(self):
        # Ensure cache is empty initially
        self.assertIsNone(cache.get(f"flat_{self.flat.pk}_occupied"))

        # Update house counts, which should set cache
        self.flat.update_house_counts()

        # Check if values are now cached
        self.assertIsNotNone(cache.get(f"flat_{self.flat.pk}_occupied"))
        self.assertIsNotNone(cache.get(f"flat_{self.flat.pk}_vacant"))
