import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_case_law


class CaseLawSyncTests(unittest.TestCase):
    def test_document_types_are_not_overstated(self):
        self.assertEqual(
            sync_case_law.classify_document_type(
                "http://publications.europa.eu/ontology/cdm#document_cjeu",
                "Judgment of the Court (Grand Chamber)",
            ),
            ("Judgment", "judicial_decision"),
        )
        self.assertEqual(
            sync_case_law.classify_document_type(
                "http://publications.europa.eu/ontology/cdm#document_cjeu",
                "Opinion of the Advocate General",
            ),
            ("Advocate General's Opinion", "advocate_general_opinion"),
        )
        self.assertEqual(
            sync_case_law.classify_document_type(
                "http://publications.europa.eu/ontology/cdm#summary_case-law",
                "Summary",
            ),
            ("Case-law summary", "case_law_reference_material"),
        )
        self.assertEqual(
            sync_case_law.classify_document_type(
                "http://publications.europa.eu/ontology/cdm#document_cjeu",
                "Document",
            ),
            ("CJEU document (type not determined)", "judicial_document_type_unverified"),
        )

    def test_court_is_inferred_from_ecli_or_case_number(self):
        self.assertEqual(
            sync_case_law.court_from_identifiers("ECLI:EU:C:2024:123", None, None),
            "Court of Justice",
        )
        self.assertEqual(
            sync_case_law.court_from_identifiers(None, "T-123/24", None),
            "General Court",
        )
        self.assertEqual(
            sync_case_law.court_from_identifiers(None, None, "Court URI"),
            "Court URI",
        )

    def test_case_url_uses_official_curia_case_page(self):
        url = sync_case_law.case_url("C-123/24")
        self.assertTrue(url.startswith("https://curia.europa.eu/juris/liste.jsf?"))
        self.assertIn("num=C-123%2F24", url)
        self.assertIn("language=en", url)
        self.assertEqual(sync_case_law.case_url(None), sync_case_law.INFOCURIA_SEARCH)

    def test_index_query_uses_official_cjeu_classes_and_date_window(self):
        work = "http://publications.europa.eu/resource/cellar/00000000-0000-0000-0000-000000000000"
        with patch.object(sync_case_law, "select", return_value=[{"work": work}]) as query:
            result = sync_case_law.fetch_index(date(2025, 1, 1), date(2025, 1, 2))
        self.assertIn(work, result)
        sparql = query.call_args.args[0]
        self.assertIn("cdm:date_creation_legacy", sparql)
        self.assertIn("document_cjeu", sparql)
        self.assertIn("summary_case-law", sparql)

    def test_hydration_preserves_ecli_parties_and_date_provenance(self):
        work = "http://publications.europa.eu/resource/cellar/00000000-0000-0000-0000-000000000000"
        metadata = {
            work: {
                "classes": {"http://publications.europa.eu/ontology/cdm#document_cjeu"},
                "eclis": {"ECLI:EU:C:2024:123"},
                "created": {"2024-03-01"},
                "documentDates": {"2024-02-29"},
                "titles": {"Judgment of the Court in Case C-123/24"},
                "caseNumbers": {"C-123/24"},
                "caseTitles": {"Example Corp v Commission"},
                "courtIds": set(),
                "subjects": {"Consumer protection"},
                "keywords": {"Consumer rights"},
                "digest": {"Consumer protection"},
            }
        }
        with patch.object(sync_case_law, "_details", return_value=metadata):
            records = sync_case_law.hydrate({work: {"work": work}})
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["id"], "ECLI:EU:C:2024:123")
        self.assertEqual(record["caseNumber"], "C-123/24")
        self.assertEqual(record["parties"], "Example Corp v Commission")
        self.assertEqual(record["court"], "Court of Justice")
        self.assertEqual(record["published"], "2024-02-29")
        self.assertEqual(record["dateType"], "CELLAR document date")
        self.assertEqual(record["sourceCategory"], "CASE_LAW")
        self.assertEqual(record["instrumentClass"], "Judgment")

    def test_duplicate_ecli_records_are_merged(self):
        records = [
            {"id": "ECLI:EU:C:2024:123", "title": "Judgment", "subjects": ["Consumer"], "keywords": [], "caseLawDigest": [], "metadataCompleteness": ["ECLI"]},
            {"id": "ECLI:EU:C:2024:123", "title": "Judgment", "subjects": ["Data protection"], "keywords": ["Privacy"], "caseLawDigest": [], "metadataCompleteness": ["date"]},
        ]
        result = sync_case_law.deduplicate(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["subjects"], ["Consumer", "Data protection"])
        self.assertEqual(result[0]["keywords"], ["Privacy"])
        self.assertEqual(result[0]["metadataCompleteness"], ["ECLI", "date"])


if __name__ == "__main__":
    unittest.main()
