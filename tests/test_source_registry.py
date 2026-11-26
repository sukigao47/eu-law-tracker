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
        homepage = registry["homepageCategories"]
        self.assertEqual(len(homepage), 13)
        self.assertEqual(sum(len(category["sources"]) for category in homepage), 40)
        self.assertEqual(
            [category["label"] for category in homepage],
            [
                "核心基础法规库",
                "能效、生态设计、可持续产品",
                "消费者保护、广告合规、绿色声明",
                "数据保护 GDPR",
                "网络安全、NIS2、CRA",
                "AI Act",
                "产品安全、市场监管、射频指令",
                "电池、循环经济、化学品、包装",
                "数字服务、数字市场",
                "立法征询、政策动态",
                "标准、合格评定、TBT通报",
                "重点成员国法律官网",
                "贸易制裁配套",
            ],
        )
        urls = [source["url"] for category in homepage for source in category["sources"]]
        self.assertEqual(len(urls), len(set(urls)))
        for category in homepage:
            for source in category["sources"]:
                self.assertTrue(source["url"].startswith("https://"))
                self.assertTrue(source["owner"])
                self.assertTrue(source["purpose"])
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
        for forbidden in ("英文标题", "智能终端全生命周期", "现行法规与近 90 天新发布文件", "法律部门／法律类别", "文件类型 / 效力类别", "效力状态", "全部业务部门", "全部法律领域", "全部文件类型", "全部状态"):
            self.assertNotIn(forbidden, html)
            self.assertNotIn(forbidden, app)


if __name__ == "__main__":
    unittest.main()
