import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from filter_catalog import classify_instrument, filter_catalog


class CatalogueClassificationTests(unittest.TestCase):
    def test_delegated_and_implementing_acts_are_distinguished(self):
        self.assertEqual(
            classify_instrument("Commission Delegated Regulation (EU) 2024/1", "R"),
            "Delegated Regulation",
        )
        self.assertEqual(
            classify_instrument("Commission Implementing Decision (EU) 2024/2", "D"),
            "Implementing Decision",
        )
        self.assertEqual(classify_instrument("Directive (EU) 2024/3", "L"), "Directive")

    def test_document_gets_multiple_departments_and_chinese_title(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "terminal-lifecycle.json"
            config.write_text(json.dumps({
                "id": "test-profile", "label": "测试目录",
                "products": ["smartphone"],
                "topics": [{
                    "id": "digital", "label": "网络安全、数据与 AI",
                    "acts": ["32024R2847"], "follow": [], "concepts": [],
                    "labels": [], "phrases": [], "context": []
                }]
            }), encoding="utf-8")
            (Path(directory) / "business-taxonomy.json").write_text(json.dumps({
                "departments": [
                    {"id": "phone", "label": "智能手机", "topics": ["digital"]},
                    {"id": "software", "label": "软件工程", "topics": ["digital"]}
                ],
                "crossCutting": [
                    {"id": "cyber", "label": "网络安全", "topics": ["digital"]}
                ]
            }), encoding="utf-8")
            (Path(directory) / "titles-zh.json").write_text(
                json.dumps({"32024R2847": "网络韧性法案"}), encoding="utf-8"
            )
            source = {
                "version": 1, "checkedAt": "2026-01-01T00:00:00+00:00",
                "documents": [{
                    "id": "32024R2847", "title": "Regulation (EU) 2024/2847",
                    "published": "2024-11-20", "entry": "2024-12-10",
                    "inForce": True, "subjects": [], "keywords": [], "concepts": []
                }]
            }
            result = filter_catalog(source, config)
            document = result["documents"][0]
            self.assertEqual(document["titleZh"], "网络韧性法案")
            self.assertEqual(set(document["departments"]), {"phone", "software"})
            self.assertEqual(document["crossCuttingTopics"], ["cyber"])
            self.assertEqual(document["instrumentClass"], "Regulation")
            self.assertTrue(document["officialUrl"].endswith("CELEX:32024R2847"))

    def test_curated_commission_guidance_is_included_in_product_conformity_topic(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "terminal-lifecycle.json"
            config.write_text(json.dumps({
                "id": "test-profile", "label": "测试目录",
                "products": ["smartphone"],
                "topics": [{
                    "id": "conformity", "label": "产品合规",
                    "acts": [], "follow": [], "documents": ["52022XC0629(04)"],
                    "concepts": [], "labels": [], "phrases": [], "context": []
                }]
            }), encoding="utf-8")
            (Path(directory) / "business-taxonomy.json").write_text(json.dumps({
                "departments": [{"id": "hardware", "label": "硬件工程", "topics": ["conformity"]}],
                "crossCutting": [{"id": "product-safety", "label": "产品安全", "topics": ["conformity"]}]
            }), encoding="utf-8")
            (Path(directory) / "titles-zh.json").write_text(
                json.dumps({"52022XC0629(04)": "欧盟产品规则实施蓝皮书（2022）"}), encoding="utf-8"
            )
            source = {
                "version": 1, "checkedAt": "2026-01-01T00:00:00+00:00",
                "documents": [{
                    "id": "52022XC0629(04)",
                    "title": "Commission notice The Blue Guide on the implementation of EU product rules 2022",
                    "published": "2022-06-29", "entry": None, "inForce": None,
                    "subjects": [], "keywords": [], "concepts": [],
                    "legalType": "Commission Notice / Guidance",
                    "instrumentClass": "Commission Notice / Guidance",
                    "bindingNature": "interpretative_guidance_non_binding",
                    "sourceCategory": "EU_SOFT_LAW"
                }]
            }
            result = filter_catalog(source, config)
            self.assertEqual(len(result["documents"]), 1)
            document = result["documents"][0]
            self.assertEqual(document["titleZh"], "欧盟产品规则实施蓝皮书（2022）")
            self.assertEqual(document["businessTopics"], ["conformity"])
            self.assertEqual(document["departments"], ["hardware"])
            self.assertEqual(document["instrumentClass"], "Commission Notice / Guidance")
            self.assertEqual(document["sourceCategory"], "EU_SOFT_LAW")

    def test_non_legislative_celex_is_not_misclassified_as_directive(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "terminal-lifecycle.json"
            config.write_text(json.dumps({
                "id": "test-profile", "label": "测试目录",
                "products": ["smartphone"],
                "topics": [{
                    "id": "marketing", "label": "营销与数字政策",
                    "acts": [], "follow": [], "concepts": [],
                    "labels": [], "phrases": ["Commission Communication"],
                    "context": []
                }]
            }), encoding="utf-8")
            source = {
                "version": 1, "checkedAt": "2026-01-01T00:00:00+00:00",
                "documents": [{
                    "id": "52024DC0123", "title": "Commission Communication on smartphone security",
                    "published": "2024-11-20", "entry": None, "inForce": None,
                    "subjects": [], "keywords": [], "concepts": [],
                    "legalType": "Commission Communication",
                    "instrumentClass": "Commission Communication",
                    "sourceCategory": "EU_SOFT_LAW",
                    "officialUrl": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A52024DC0123"
                }]
            }
            result = filter_catalog(source, config)
            self.assertEqual(len(result["documents"]), 1)
            document = result["documents"][0]
            self.assertEqual(document["legalType"], "Commission Communication")
            self.assertEqual(document["instrumentClass"], "Commission Communication")
            self.assertEqual(document["sourceCategory"], "EU_SOFT_LAW")

    def test_case_law_keeps_judicial_document_type_separate_from_legislation(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "terminal-lifecycle.json"
            config.write_text(json.dumps({
                "id": "test-profile", "label": "测试目录",
                "products": ["smartphone"],
                "topics": [{
                    "id": "consumer", "label": "消费者保护",
                    "acts": [], "follow": [], "concepts": [],
                    "labels": [], "phrases": ["consumer protection"],
                    "context": []
                }]
            }), encoding="utf-8")
            source = {
                "version": 1, "checkedAt": "2026-01-01T00:00:00+00:00",
                "documents": [{
                    "id": "ECLI:EU:C:2024:123",
                    "title": "Judgment of the Court on consumer protection",
                    "published": "2024-11-20", "entry": None, "inForce": None,
                    "subjects": ["Consumer protection"], "keywords": [], "concepts": [],
                    "legalType": "Judgment", "instrumentClass": "Judgment",
                    "bindingNature": "judicial_decision", "sourceCategory": "CASE_LAW",
                    "officialUrl": "https://curia.europa.eu/juris/liste.jsf?num=C-123%2F24&language=en"
                }]
            }
            result = filter_catalog(source, config)
            self.assertEqual(len(result["documents"]), 1)
            document = result["documents"][0]
            self.assertEqual(document["legalType"], "Judgment")
            self.assertEqual(document["instrumentClass"], "Judgment")
            self.assertEqual(document["sourceCategory"], "CASE_LAW")
            self.assertEqual(document["id"], "ECLI:EU:C:2024:123")


if __name__ == "__main__":
    unittest.main()
