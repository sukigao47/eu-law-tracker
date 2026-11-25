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


if __name__ == "__main__":
    unittest.main()
