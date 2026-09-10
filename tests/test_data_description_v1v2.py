"""Tests for data description v1 to v2 upgrade functions"""

import unittest
from copy import deepcopy
from unittest.mock import patch

from aind_data_schema.components.identifiers import Person
from aind_data_schema_models.registries import Registry

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2


class TestDataDescriptionV1V2People(unittest.TestCase):
    """Test person conversion and identifier preservation."""

    def setUp(self):
        """Set up the upgrader and a v1 person with an ORCID."""
        self.upgrader = DataDescriptionV1V2()
        self.person = {
            "name": "Jane Smith",
            "abbreviation": "JS",
            "registry": {
                "name": "Open Researcher and Contributor ID",
                "abbreviation": "ORCID",
            },
            "registry_identifier": "0000-0002-1825-0097",
        }

    def test_coerce_person_dictionaries(self):
        """Preserve identifiers and normalize registries without changing input."""
        expected = Person(name=self.person["name"], registry_identifier=self.person["registry_identifier"])
        cases = [
            ("v1", self.person, expected),
            ("v2", expected.model_dump(), expected),
            ("v2_json", expected.model_dump(mode="json"), expected),
            ("null_registry", {**self.person, "registry": None}, expected),
            ("missing_registry", {key: value for key, value in self.person.items() if key != "registry"}, expected),
            ("name_only", {"name": self.person["name"]}, Person(name=self.person["name"])),
            (
                "non_orcid_registry",
                {"name": "Jane Smith", "registry": Registry.RRID.value, "registry_identifier": "example-id"},
                Person(name="Jane Smith", registry=Registry.RRID, registry_identifier="example-id"),
            ),
        ]
        for name, value, expected_person in cases:
            with self.subTest(name=name):
                original = deepcopy(value)
                self.assertEqual(self.upgrader._coerce_person(value), expected_person)
                self.assertEqual(value, original)

    def test_coerce_person_objects_and_strings(self):
        """Keep existing Person objects unchanged and support plain names."""
        person = Person(name=self.person["name"], registry_identifier=self.person["registry_identifier"])
        self.assertIs(self.upgrader._coerce_person(person), person)
        self.assertEqual(self.upgrader._coerce_person("Jane Smith"), Person(name="Jane Smith"))

    def test_upgrade_preserves_investigator_and_fundee_identifiers(self):
        """Retain person identifiers through investigator and both funding paths."""
        expected = Person(name=self.person["name"], registry_identifier=self.person["registry_identifier"])
        for funder, count in [("Allen Institute", 1), ("Allen Institute, Allen Institute", 2)]:
            with self.subTest(funder=funder):
                data = {
                    "name": "example",
                    "data_level": "raw",
                    "investigators": [deepcopy(self.person), expected.model_dump(mode="json"), expected, "John Smith"],
                    "funding_source": [
                        {
                            "funder": funder,
                            "fundee": [deepcopy(self.person), expected.model_dump(mode="json"), expected, "John Smith"],
                        }
                    ],
                }
                original = deepcopy(data)
                result = self.upgrader.upgrade(data, "2.0.0")
                expected_people = [expected, expected, expected, Person(name="John Smith")]
                self.assertEqual(
                    result["investigators"], [person.model_dump(mode="json") for person in expected_people]
                )
                self.assertEqual(len(result["funding_source"]), count)
                for funding in result["funding_source"]:
                    self.assertEqual(funding["fundee"], [person.model_dump() for person in expected_people])
                self.assertEqual(data, original)

    def test_unsupported_investigator(self):
        """Keep rejecting unsupported investigator values."""
        with self.assertRaisesRegex(ValueError, "Unsupported investigator type"):
            self.upgrader._get_investigators({"investigators": [123]})


class TestDataDescriptionV1V2FundingSource(unittest.TestCase):
    """Test the DataDescriptionV1V2 funding source upgrade"""

    def setUp(self):
        """Set up the upgrader instance for testing"""
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
        with patch("aind_metadata_upgrader.data_description.v1v2.FAKE_MISSING_DATA", False):
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


class TestDataDescriptionSourceData(unittest.TestCase):
    """Test source-data parent lookup behavior."""

    def test_reuses_parent_lookup_for_repeated_chain(self):
        """Repeated upgrades of the same parent chain should reuse lookups."""
        from aind_metadata_upgrader.data_description import v1v2

        v1v2._parent_data_description_cache_clear()
        with patch.object(v1v2.client, "retrieve_docdb_records") as retrieve:
            retrieve.side_effect = [
                [{"data_description": {"data_level": "derived", "input_data_name": "raw_asset"}}],
                [{"data_description": {"data_level": "raw", "name": "raw_asset"}}],
            ]
            data = {"data_level": "derived", "input_data_name": "derived_asset_name_2024_extra"}

            first = self._source_data(data)
            second = self._source_data(data)

        self.assertEqual(first, ["raw_asset", "raw_asset", "derived_asset_name_2024_extra"])
        self.assertEqual(second, first)
        self.assertEqual(retrieve.call_count, 2)

    def _source_data(self, data):
        """Call the source-data upgrade helper."""
        return DataDescriptionV1V2()._upgrade_source_data(data)


if __name__ == "__main__":
    unittest.main()
