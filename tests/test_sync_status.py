import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync


class NonCurrentLegislationIndexTests(unittest.TestCase):
    @patch("sync.select")
    def test_non_current_index_queries_cellar_false_records(self, select):
        work = "https://publications.europa.eu/resource/cellar/01234567-89ab-cdef-0123-456789abcdef"
        select.return_value = [{"id": "32000R0001", "work": work}]

        result = sync.not_in_force_index()

        self.assertEqual(result, {"32000R0001": work})
        query = select.call_args.args[0]
        self.assertIn("cdm:resource_legal_in-force false", query)
        self.assertIn('FILTER(REGEX(STR(?id)', query)

    def test_wanted_index_includes_non_current_and_recent_records(self):
        current = {"32024R0001": "https://publications.europa.eu/resource/cellar/current"}
        non_current = {"32000R0002": "https://publications.europa.eu/resource/cellar/repealed"}
        recent = {
            "32026R0003": {
                "work": "https://publications.europa.eu/resource/cellar/recent",
                "published": "2026-11-25",
            }
        }

        result = sync.wanted_index(current, non_current, recent)

        self.assertEqual(result["32024R0001"], current["32024R0001"])
        self.assertEqual(result["32000R0002"], non_current["32000R0002"])
        self.assertEqual(result["32026R0003"], recent["32026R0003"]["work"])

    def test_indexed_non_current_flag_is_preserved_as_false(self):
        record = {"inForce": True}

        sync.apply_indexed_in_force(
            "32000R0002",
            record,
            {},
            {"32000R0002": "https://publications.europa.eu/resource/cellar/repealed"},
        )

        self.assertIs(record["inForce"], False)

    @patch("sync.select")
    def test_details_tolerates_historical_work_without_english_title(self, select):
        work = "https://publications.europa.eu/resource/cellar/01234567-89ab-cdef-0123-456789abcdef"
        select.return_value = [{
            "work": work,
            "field": "subject",
            "value": "Consumer protection",
        }]

        result = sync.details([("32000R0002", work)])

        self.assertEqual(result["32000R0002"]["title"], "")
        self.assertEqual(result["32000R0002"]["subjects"], ["Consumer protection"])

    def test_indexed_current_flag_takes_precedence(self):
        record = {"inForce": False}
        index = {"32024R0001": "https://publications.europa.eu/resource/cellar/current"}

        sync.apply_indexed_in_force("32024R0001", record, index, {})

        self.assertIs(record["inForce"], True)


if __name__ == "__main__":
    unittest.main()
