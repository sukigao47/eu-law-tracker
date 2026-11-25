import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfficialSourceRegistryTests(unittest.TestCase):
    def test_registry_separates_related_material_categories(self):
        registry = json.loads((ROOT / "config/source-registry.json").read_text(encoding="utf-8"))
        categories = {item["id"]: item for item in registry["categories"]}
        self.assertEqual(
            set(categories),
            {"soft_law", "oj_c_series", "case_law", "commission_guidance", "technical_standards"},
        )
        self.assertEqual(categories["soft_law"]["status"], "automated_partial")
        self.assertEqual(categories["oj_c_series"]["status"], "automated_partial")
        self.assertEqual(categories["case_law"]["status"], "automated_partial")
        for category_id in ("commission_guidance", "technical_standards"):
            self.assertEqual(categories[category_id]["status"], "reference_only")
        for category in categories.values():
            self.assertTrue(category["sources"])
            for source in category["sources"]:
                self.assertTrue(source["url"].startswith("https://"))
                self.assertTrue(source["name"])
                self.assertTrue(source["purpose"])

    def test_standards_are_explicitly_not_legislation(self):
        registry = json.loads((ROOT / "config/source-registry.json").read_text(encoding="utf-8"))
        standards = next(item for item in registry["categories"] if item["id"] == "technical_standards")
        self.assertIn("not EU legislation", standards["description"])

    def test_user_interface_omits_requested_copy(self):
        html = (ROOT / "site/index.html").read_text(encoding="utf-8")
        app = (ROOT / "site/app.js").read_text(encoding="utf-8")
        for forbidden in ("英文标题", "智能终端全生命周期", "现行法规与近 90 天新发布文件"):
            self.assertNotIn(forbidden, html)
            self.assertNotIn(forbidden, app)


if __name__ == "__main__":
    unittest.main()
