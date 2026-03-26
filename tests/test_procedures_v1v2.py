"""Unit tests for procedures upgrader v1v2."""

import unittest

from aind_metadata_upgrader.procedures.v1v2 import ProceduresUpgraderV1V2


class TestProceduresUpgraderV1V2(unittest.TestCase):
    """Test cases for ProceduresUpgraderV1V2."""

    def test_upgrade_subject_procedure_wraps_standalone_perfusion_as_surgery(self):
        """Standalone perfusion records should be wrapped into a Surgery object."""
        upgrader = ProceduresUpgraderV1V2()
        upgrader.subject_id = "658355"
        perfusion_data = {
            "anaesthesia": None,
            "animal_weight_post": None,
            "animal_weight_prior": None,
            "end_date": "2023-01-26",
            "experimenter_full_name": "LAS",
            "iacuc_protocol": None,
            "notes": None,
            "output_specimen_ids": ["658355"],
            "procedure_type": "Perfusion",
            "protocol_id": "unknown",
            "start_date": "2023-01-26",
            "weight_unit": "gram",
        }

        upgraded = upgrader._upgrade_subject_procedure(perfusion_data)

        self.assertIn("procedures", upgraded)
        self.assertEqual(len(upgraded["procedures"]), 1)
        self.assertEqual(upgraded["procedures"][0]["output_specimen_ids"], ["658355"])
        self.assertIn("experimenters", upgraded)
        self.assertEqual(upgraded["experimenters"], ["LAS"])


if __name__ == "__main__":
    unittest.main()
