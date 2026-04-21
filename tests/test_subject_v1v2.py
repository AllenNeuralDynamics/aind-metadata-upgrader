"""Tests for subject v1v2 upgrade functionality"""

import unittest
from pathlib import Path

from aind_metadata_upgrader.subject.v1v2 import SubjectUpgraderV1V2

RECORDS_DIR = Path(__file__).parent / "records"


class TestSubjectV1V2Upgrade(unittest.TestCase):
    """Test subject v1v2 upgrade functionality"""

    def test_subject_upgrade_with_nested_breeding_info(self):
        """Test that breeding info is preserved when nested in a breeding_info object"""
        subject_data = {
            "subject_id": "776241",
            "sex": "Female",
            "date_of_birth": "2024-11-06",
            "genotype": "Syt17-Cre_NO14/wt",
            "schema_version": "1.0.3",
            "species": {
                "name": "Mus musculus",
                "registry": {"name": "National Center for Biotechnology Information", "abbreviation": "NCBI"},
                "registry_identifier": "NCBI:txid10090",
            },
            "breeding_info": {
                "maternal_id": "756189",
                "maternal_genotype": "Syt17-Cre_NO14/wt",
                "paternal_id": "755350",
                "paternal_genotype": "wt/wt",
            },
            "source": {
                "name": "Allen Institute",
                "abbreviation": "AI",
                "registry": {"name": "Research Organization Registry", "abbreviation": "ROR"},
                "registry_identifier": "03cpe7c52",
            },
        }

        upgrader = SubjectUpgraderV1V2()
        result = upgrader.upgrade(subject_data, "2.1.2")

        # Verify breeding info fields are preserved
        self.assertIsNotNone(result["subject_details"]["breeding_info"])
        self.assertEqual(result["subject_details"]["breeding_info"]["maternal_id"], "756189")
        self.assertEqual(result["subject_details"]["breeding_info"]["maternal_genotype"], "Syt17-Cre_NO14/wt")
        self.assertEqual(result["subject_details"]["breeding_info"]["paternal_id"], "755350")
        self.assertEqual(result["subject_details"]["breeding_info"]["paternal_genotype"], "wt/wt")

    def test_subject_upgrade_with_flat_breeding_info(self):
        """Test that breeding info is preserved when fields are at the top level (backward compatibility)"""
        subject_data = {
            "subject_id": "12345",
            "sex": "Male",
            "date_of_birth": "2022-11-22",
            "genotype": "Emx1-IRES-Cre/wt;Camk2a-tTA/wt;Ai93(TITL-GCaMP6f)/wt",
            "schema_version": "1.0.3",
            "species": {
                "name": "Mus musculus",
                "registry": {"name": "National Center for Biotechnology Information", "abbreviation": "NCBI"},
                "registry_identifier": "NCBI:txid10090",
            },
            "maternal_id": "546543",
            "maternal_genotype": "Emx1-IRES-Cre/wt; Camk2a-tTa/Camk2a-tTA",
            "paternal_id": "232323",
            "paternal_genotype": "Ai93(TITL-GCaMP6f)/wt",
            "source": {
                "name": "Allen Institute",
                "abbreviation": "AI",
                "registry": {"name": "Research Organization Registry", "abbreviation": "ROR"},
                "registry_identifier": "03cpe7c52",
            },
        }

        upgrader = SubjectUpgraderV1V2()
        result = upgrader.upgrade(subject_data, "2.1.2")

        # Verify breeding info fields are preserved
        self.assertIsNotNone(result["subject_details"]["breeding_info"])
        self.assertEqual(result["subject_details"]["breeding_info"]["maternal_id"], "546543")
        self.assertEqual(
            result["subject_details"]["breeding_info"]["maternal_genotype"], "Emx1-IRES-Cre/wt; Camk2a-tTa/Camk2a-tTA"
        )
        self.assertEqual(result["subject_details"]["breeding_info"]["paternal_id"], "232323")
        self.assertEqual(result["subject_details"]["breeding_info"]["paternal_genotype"], "Ai93(TITL-GCaMP6f)/wt")

    def test_subject_upgrade_without_breeding_info(self):
        """Test that breeding info is None when no breeding info is provided"""
        subject_data = {
            "subject_id": "99999",
            "sex": "Female",
            "date_of_birth": "2023-01-01",
            "genotype": "wt/wt",
            "schema_version": "1.0.3",
            "species": {
                "name": "Mus musculus",
                "registry": {"name": "National Center for Biotechnology Information", "abbreviation": "NCBI"},
                "registry_identifier": "NCBI:txid10090",
            },
            "source": {
                "name": "Allen Institute",
                "abbreviation": "AI",
                "registry": {"name": "Research Organization Registry", "abbreviation": "ROR"},
                "registry_identifier": "03cpe7c52",
            },
        }

        upgrader = SubjectUpgraderV1V2()
        result = upgrader.upgrade(subject_data, "2.1.2")

        # Verify breeding info is None
        self.assertIsNone(result["subject_details"]["breeding_info"])


if __name__ == "__main__":
    unittest.main()
