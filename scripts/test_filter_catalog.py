import json
import tempfile
import unittest
from pathlib import Path

from filter_catalog import classify_celex, filter_catalog


class DocumentClassificationTests(unittest.TestCase):
    def test_binding_legislation(self):
        self.assertEqual(classify_celex("32023R1669")["legalEffect"], "binding")
        self.assertEqual(classify_celex("32022L2555")["legalEffect"], "binding")
        self.assertEqual(classify_celex("32024D1234")["legalEffect"], "binding")

    def test_non_binding_recommendation_and_opinion(self):
        self.assertEqual(classify_celex("32024H0123")["legalEffect"], "non-binding")
        self.assertEqual(classify_celex("32024A0123")["legalEffect"], "non-binding")

    def test_preparatory_and_soft_law(self):
        self.assertEqual(classify_celex("52024PC0139")["legalEffect"], "preparatory")
        self.assertEqual(
            classify_celex("52024DC0139", "Commission communication on connected products")["legalEffect"],
            "non-binding",
        )

    def test_oj_c_and_judicial_documents(self):
        self.assertEqual(classify_celex("C202503118")["legalEffect"], "informational")
        self.assertEqual(classify_celex("62024CJ0123")["legalEffect"], "judicial")

    def test_filter_adds_searchable_metadata(self):
        profile = {
            "id": "test-profile",
            "label": "测试主题",
            "products": ["smartphone"],
            "topics": [{
                "id": "devices", "label": "终端产品",
                "acts": [], "follow": [], "concepts": [], "labels": [],
                "phrases": ["smartphone"], "context": ["product safety"],
            }],
        }
        catalogue = {
            "version": 2, "checkedAt": "2026-11-25T00:00:00+00:00",
            "through": "2026-11-25", "documents": [{
                "id": "32023R1669", "title": "Commission Regulation (EU) 2023/1669 on smartphones",
                "published": "2023-09-01", "inForce": True, "entry": "2023-09-21",
                "subjects": [], "keywords": [], "concepts": [],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            result = filter_catalog(catalogue, path)
        self.assertEqual(len(result["documents"]), 1)
        record = result["documents"][0]
        self.assertEqual(record["titleEn"], record["title"])
        self.assertEqual(record["documentTypeLabel"], "Regulation")
        self.assertEqual(record["legalEffect"], "binding")
        self.assertEqual(record["businessTopics"], ["devices"])
        self.assertIn("eur-lex.europa.eu", record["eurlexUrl"])


if __name__ == "__main__":
    unittest.main()
