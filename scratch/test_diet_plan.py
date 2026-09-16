import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from application import app, Session
from application.models import User, UserProfile, UserPersonalHealth, HealthReport
from application.diet_engine import generate_diet_guidance
from application.pdf_generator import generate_diet_pdf

class TestDietPlan(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_diet_guidance_generation(self):
        class DummyUser:
            id = 1
            username = "testuser"
            email = "test@vitasense.com"

        class DummyProfile:
            diet = "Vegan"

        class DummyHealth:
            known_allergies = "Peanuts"

        class DummyReport:
            created_at = "Sep 16, 2026"
            title = "Anemia Risk & Vitamin B12 Checkup"
            selected_modules_json = '["anemia", "b12"]'

        guidance = generate_diet_guidance(DummyUser(), DummyProfile(), DummyHealth(), DummyReport())
        
        self.assertEqual(guidance["diet_pref"], "Vegan")
        self.assertTrue(guidance["has_allergies"])
        self.assertEqual(guidance["known_allergies"], "Peanuts")
        self.assertEqual(len(guidance["guidance_blocks"]), 2)

        # Ensure no animal products in vegan guidance
        b12_block = next(b for b in guidance["guidance_blocks"] if b["id"] == "b12")
        items = b12_block["categories"][0]["items"]
        self.assertFalse(any("Eggs" in i or "Fish" in i or "Dairy" in i for i in items))

    def test_pdf_generation(self):
        class DummyUser:
            id = 1
            username = "testuser"
            email = "test@vitasense.com"

        class DummyProfile:
            diet = "Vegetarian"

        class DummyHealth:
            known_allergies = ""

        class DummyReport:
            created_at = "Sep 16, 2026"
            title = "Vitamin D Checkup"
            selected_modules_json = '["vitamin_d"]'

        guidance = generate_diet_guidance(DummyUser(), DummyProfile(), DummyHealth(), DummyReport())
        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_diet.pdf"))
        
        try:
            generate_diet_pdf(out_path, DummyUser.username, DummyUser.email, guidance)
            self.assertTrue(os.path.exists(out_path))
            self.assertGreater(os.path.getsize(out_path), 0)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

if __name__ == '__main__':
    unittest.main()
