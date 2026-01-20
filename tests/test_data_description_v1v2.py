"""Tests for data description v1 to v2 upgrade functions"""

import unittest
from unittest.mock import patch

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2


class TestDataDescriptionV1V2FundingSource(unittest.TestCase):
    """Test the DataDescriptionV1V2 funding source upgrade"""

    def setUp(self):
        self.upgrader = DataDescriptionV1V2()

    def test_funding_source_as_list(self):
        """Test when funding_source is a list (current expected format)"""
        data = {
            "funding_source": [
                {
                    "funder": {
                        "name": "Allen Institute",
                        "abbreviation": "AI",
                        "registry": {
                            "name": "Research Organization Registry",
                            "abbreviation": "ROR",
                        },
                        "registry_identifier": "03cpe7c52",
                    },
                    "grant_number": None,
                    "fundee": "Bowen Tan",
                }
            ]
        }
        result = self.upgrader._get_funding_source(data)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("funder", result[0])
        self.assertIn("fundee", result[0])

    def test_funding_source_as_single_object(self):
        """Test when funding_source is a single object instead of a list"""
        data = {
            "funding_source": {
                "funder": {
                    "name": "Allen Institute",
                    "abbreviation": "AI",
                    "registry": {
                        "name": "Research Organization Registry",
                        "abbreviation": "ROR",
                    },
                    "registry_identifier": "03cpe7c52",
                },
                "grant_number": None,
                "fundee": "Bowen Tan",
            }
        }
        result = self.upgrader._get_funding_source(data)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIn("funder", result[0])
        self.assertIn("fundee", result[0])
        # Check that fundee was converted properly
        self.assertEqual(result[0]["fundee"][0]["name"], "Bowen Tan")

    def test_funding_source_empty_list(self):
        """Test when funding_source is an empty list"""
        data = {"funding_source": []}
        with patch('aind_metadata_upgrader.data_description.v1v2.FAKE_MISSING_DATA', False):
            result = self.upgrader._get_funding_source(data)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    def test_funding_source_missing(self):
        """Test when funding_source is missing"""
        data = {}
        result = self.upgrader._get_funding_source(data)
        self.assertIsInstance(result, list)

    def test_funding_source_with_string_fundee(self):
        """Test when fundee is a string"""
        data = {
            "funding_source": {
                "funder": "AIND",
                "grant_number": "12345",
                "fundee": "Bowen Tan",
            }
        }
        result = self.upgrader._get_funding_source(data)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fundee"][0]["name"], "Bowen Tan")
        self.assertEqual(result[0]["grant_number"], "12345")

    def test_funding_source_with_multiple_fundees_string(self):
        """Test when fundee is a comma-separated string"""
        data = {
            "funding_source": {
                "funder": "AIND",
                "grant_number": None,
                "fundee": "Bowen Tan, John Smith",
            }
        }
        result = self.upgrader._get_funding_source(data)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["fundee"]), 2)
        self.assertEqual(result[0]["fundee"][0]["name"], "Bowen Tan")
        self.assertEqual(result[0]["fundee"][1]["name"], "John Smith")


if __name__ == "__main__":
    unittest.main()
