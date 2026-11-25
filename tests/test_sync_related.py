import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_related


class RelatedMaterialSyncTests(unittest.TestCase):
    def test_soft_law_celex_descriptors_are_classified(self):
        self.assertEqual(
            sync_related.classify_soft_law("32024H0001", "Commission Recommendation"),
            ("Recommendation", "non_binding_instrument"),
        )
        self.assertEqual(
            sync_related.classify_soft_law("32024A0001", "Opinion"),
            ("Opinion", "non_binding_instrument"),
        )
        self.assertEqual(
            sync_related.classify_soft_law("52024DC0123", "Communication from the Commission"),
            ("Commission Communication", "non_legislative_document"),
        )
        self.assertEqual(
            sync_related.classify_soft_law("52024DC0124", "Report from the Commission"),
            ("Commission Report", "non_legislative_document"),
        )
        self.assertEqual(
            sync_related.classify_soft_law("52024AE0001", "EESC Opinion"),
            ("Institutional Opinion", "non_legislative_document"),
        )
        self.assertEqual(
            sync_related.classify_soft_law("52024JC0001", "Joint Communication"),
            ("Joint Communication", "non_legislative_document"),
        )
        self.assertTrue(sync_related.SOFT_LAW_CELEX.fullmatch("52024SC0001"))

    def test_official_url_encodes_c_series_celex(self):
        url = sync_related.official_url("C/2025/03118")
        self.assertIn("CELEX%3AC%2F2025%2F03118", url)

    def test_deduplication_keeps_both_collection_tags(self):
        soft = [{
            "id": "32024H0001", "title": "Commission Recommendation",
            "sourceCategory": "EU_SOFT_LAW", "published": "2024-01-01",
            "sourceCollections": ["EU_SOFT_LAW"],
        }]
        ojc = [{
            "id": "32024H0001", "title": "Commission Recommendation",
            "sourceCategory": "OJ_C_SERIES", "published": "2024-01-01",
            "sourceCollections": ["OJ_C_SERIES"],
        }]
        result = sync_related.deduplicate_materials(soft, ojc)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sourceCollections"], ["EU_SOFT_LAW", "OJ_C_SERIES"])

    def test_hydration_tolerates_missing_title_and_metadata(self):
        index = {
            "C/2025/03118": {
                "id": "C/2025/03118",
                "work": "http://publications.europa.eu/resource/cellar/00000000-0000-0000-0000-000000000000",
                "published": "2025-01-01",
            }
        }
        with patch.object(sync_related, "details", return_value={}):
            records = sync_related.hydrate(index, "OJ_C_SERIES")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "")
        self.assertEqual(records[0]["metadataCompleteness"], "title_missing")
        self.assertEqual(records[0]["bindingNature"], "not_determined_from_series")

    def test_oj_c_query_is_limited_to_official_c_collection(self):
        row = {
            "id": "C/2025/03118",
            "work": "http://publications.europa.eu/resource/cellar/00000000-0000-0000-0000-000000000000",
            "published": "2025-01-01",
        }
        with patch.object(sync_related, "select", return_value=[row]) as query:
            result = sync_related.fetch_oj_c_series(
                sync_related.date(2025, 1, 1), sync_related.date(2025, 1, 2)
            )
        self.assertIn("C/2025/03118", result)
        self.assertIn("OJ-C", query.call_args.args[0])
        self.assertIn('STR(?id) != ""', query.call_args.args[0])

    def test_soft_law_query_uses_xml_schema_compatible_regex(self):
        with patch.object(sync_related, "select", return_value=[]) as query:
            sync_related.fetch_soft_law(
                sync_related.date(2025, 1, 1), sync_related.date(2025, 1, 2)
            )
        sparql = query.call_args.args[0]
        self.assertIn("REGEX(STR(?id)", sparql)
        self.assertNotIn("(?:", sparql)


if __name__ == "__main__":
    unittest.main()
