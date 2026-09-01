import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("pipeline", Path(__file__).parents[1] / "scripts" / "update_tracker.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_state_parsing(self):
        self.assertEqual(pipeline.states_from("Distributed in Washington, TX and CA"), ["CA", "TX", "WA"])
        self.assertEqual(pipeline.states_from("Distributed nationwide"), ["US"])

    def test_priority_allergens(self):
        self.assertEqual(pipeline.allergens_from("undeclared sesame and cashews"), ["tree nuts", "sesame"])

    def test_categories(self):
        self.assertEqual(pipeline.product_category("recalled infant stroller"), "Baby & child")
        self.assertEqual(pipeline.product_category("hockey helmet can crack"), "Sports & outdoors")

    def test_pet_food_requires_pet_food_context(self):
        self.assertTrue(pipeline.is_pet_food("Salmonella risk in dog food and cat treats"))
        self.assertFalse(pipeline.is_pet_food("Chocolate shapes: Cat, Teddy Bear, and Easter Bunny"))

    def test_actions_are_section_specific(self):
        self.assertIn("Do not consume", pipeline.action_for("food", "possible Salmonella"))
        self.assertIn("Stop using", pipeline.action_for("products", "fire hazard"))


if __name__ == "__main__":
    unittest.main()
