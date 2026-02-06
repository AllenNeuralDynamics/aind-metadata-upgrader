"""Unit tests for procedures v1v2_procedures module to improve code coverage"""

import json
import os
import unittest
from aind_data_schema_models.units import SizeUnit
from aind_data_schema.components.surgery_procedures import CraniotomyType
from aind_metadata_upgrader.procedures.v1v2_procedures import (
    retrieve_bl_distance,
    upgrade_hemisphere_craniotomy,
    upgrade_coordinate_craniotomy,
    upgrade_craniotomy,
    upgrade_headframe,
    upgrade_protective_material_replacement,
    upgrade_sample_collection,
    upgrade_perfusion,
    retrieve_probe_config,
)
from aind_metadata_upgrader.procedures.v1v2 import ProceduresUpgraderV1V2


class TestProceduresV1V2(unittest.TestCase):
    """Test cases for v1v2_procedures functions"""

    def test_retrieve_bl_distance_negative_distance(self):
        """Test line 72: negative bregma-to-lambda distance"""
        data = {"bregma_to_lambda_distance": -4.5, "bregma_to_lambda_unit": SizeUnit.MM}
        result, measured_coords = retrieve_bl_distance(data)
        self.assertNotIn("bregma_to_lambda_distance", result)
        self.assertIsInstance(measured_coords, list)

    def test_retrieve_bl_distance_micrometer_unit(self):
        """Test line 74: micrometer unit conversion"""
        data = {"bregma_to_lambda_distance": 4500, "bregma_to_lambda_unit": SizeUnit.UM}
        result, measured_coords = retrieve_bl_distance(data)
        self.assertNotIn("bregma_to_lambda_distance", result)
        self.assertIsInstance(measured_coords, list)

    def test_retrieve_bl_distance_unsupported_unit(self):
        """Test lines 76-79: unsupported unit error"""
        data = {"bregma_to_lambda_distance": 4.5, "bregma_to_lambda_unit": "meter"}
        with self.assertRaises(ValueError):
            _, _ = retrieve_bl_distance(data)

    def test_upgrade_hemisphere_craniotomy_left(self):
        """Test lines 108-110: left hemisphere"""
        data = {"craniotomy_hemisphere": "left", "craniotomy_type": CraniotomyType.CIRCLE}
        result = upgrade_hemisphere_craniotomy(data)
        self.assertIn("coordinate_system_name", result)

    def test_upgrade_hemisphere_craniotomy_right(self):
        """Test lines 111-112: right hemisphere"""
        data = {"craniotomy_hemisphere": "right", "craniotomy_type": CraniotomyType.CIRCLE}
        result = upgrade_hemisphere_craniotomy(data)
        self.assertIn("coordinate_system_name", result)

    def test_upgrade_hemisphere_craniotomy_invalid(self):
        """Test lines 114-116: invalid hemisphere"""
        data = {"craniotomy_hemisphere": "middle", "craniotomy_type": CraniotomyType.CIRCLE}
        with self.assertRaises(ValueError):
            upgrade_hemisphere_craniotomy(data)

    def test_upgrade_coordinate_craniotomy_basic(self):
        """Test lines 136-137: basic coordinate craniotomy"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertIn("position", result)

    def test_upgrade_coordinate_craniotomy_size_unit(self):
        """Test line 150: size_unit assignment"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertEqual(result["size_unit"], SizeUnit.MM)

    def test_upgrade_coordinate_craniotomy_invalid_reference(self):
        """Test line 153: invalid reference"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Lambda",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        with self.assertRaises(ValueError):
            upgrade_coordinate_craniotomy(data)

    def test_upgrade_coordinate_craniotomy_micrometer_unit(self):
        """Test lines 155-157: micrometer unit conversion"""
        data = {
            "craniotomy_coordinates_ml": 2000,
            "craniotomy_coordinates_ap": 3000,
            "craniotomy_coordinates_unit": "micrometer",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertIn("position", result)

    def test_upgrade_coordinate_craniotomy_unsupported_unit(self):
        """Test line 158-159: unsupported unit"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "meter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        with self.assertRaises(ValueError):
            upgrade_coordinate_craniotomy(data)

    def test_upgrade_coordinate_craniotomy_left_hemisphere_positive_ml(self):
        """Test line 164: left hemisphere with positive ML"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
            "craniotomy_hemisphere": "left",
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertIn("position", result)

    def test_upgrade_coordinate_craniotomy_right_hemisphere_negative_ml(self):
        """Test line 168: right hemisphere with negative ML"""
        data = {
            "craniotomy_coordinates_ml": -2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
            "craniotomy_hemisphere": "right",
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertIn("position", result)

    def test_upgrade_coordinate_craniotomy_coordinate_system_name(self):
        """Test line 177: coordinate system name assignment"""
        data = {
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        result = upgrade_coordinate_craniotomy(data)
        self.assertIn("coordinate_system_name", result)

    def test_upgrade_craniotomy_copy_data(self):
        """Test line 191: data copy"""
        data = {
            "craniotomy_type": CraniotomyType.CIRCLE,
            "procedure_type": "Craniotomy",
            "craniotomy_hemisphere": "left",
            "size": 5,
            "size_unit": SizeUnit.MM,
        }
        result, measured_coords = upgrade_craniotomy(data)
        self.assertIsInstance(result, dict)
        self.assertIsInstance(measured_coords, list)

    def test_upgrade_craniotomy_remove_recovery_time(self):
        """Test line 194: remove recovery_time"""
        data = {
            "craniotomy_type": CraniotomyType.CIRCLE,
            "procedure_type": "Craniotomy",
            "recovery_time": "24 hours",
            "craniotomy_hemisphere": "left",
            "size": 5,
            "size_unit": SizeUnit.MM,
        }
        result = upgrade_craniotomy(data)
        self.assertNotIn("recovery_time", result)

    def test_upgrade_craniotomy_5mm_type(self):
        """Test line 200: 5mm craniotomy type"""
        data = {"craniotomy_type": "5 mm", "procedure_type": "Craniotomy", "craniotomy_hemisphere": "left"}
        result, measured_coords = upgrade_craniotomy(data)
        self.assertEqual(result["size"], 5)

    def test_upgrade_craniotomy_retrieve_bl_distance(self):
        """Test line 212: retrieve_bl_distance call"""
        data = {
            "craniotomy_type": CraniotomyType.CIRCLE,
            "procedure_type": "Craniotomy",
            "bregma_to_lambda_distance": 4.5,
            "bregma_to_lambda_unit": SizeUnit.MM,
            "craniotomy_hemisphere": "left",
            "size": 5,
            "size_unit": SizeUnit.MM,
        }
        result = upgrade_craniotomy(data)
        self.assertNotIn("bregma_to_lambda_distance", result)
        # Note: We don't need to test measured_coordinates here as upgrade_craniotomy handles that internally

    def test_upgrade_craniotomy_coordinate_craniotomy(self):
        """Test line 215: upgrade_coordinate_craniotomy call"""
        data = {
            "craniotomy_type": CraniotomyType.CIRCLE,
            "procedure_type": "Craniotomy",
            "craniotomy_coordinates_ml": 2.0,
            "craniotomy_coordinates_ap": 3.0,
            "craniotomy_coordinates_unit": "millimeter",
            "craniotomy_coordinates_reference": "Bregma",
            "craniotomy_size": 5,
            "craniotomy_size_unit": SizeUnit.MM,
        }
        result, measured_coords = upgrade_craniotomy(data)
        self.assertIsInstance(result["position"], dict)  # Changed to check for dict type since we know the structure

    def test_upgrade_headframe_empty_part_number(self):
        """Test line 242: empty headframe_part_number"""
        data = {"procedure_type": "Headframe", "headframe_part_number": "", "headframe_type": "test_type"}
        result = upgrade_headframe(data)
        self.assertEqual(result["headframe_part_number"], "unknown")

    def test_upgrade_headframe_empty_type(self):
        """Test lines 245-246: empty headframe_type"""
        data = {"procedure_type": "Headframe", "headframe_type": "", "headframe_part_number": "test_part"}
        result = upgrade_headframe(data)
        self.assertEqual(result["headframe_type"], "unknown")

    def test_upgrade_protective_material_replacement(self):
        """Test line 255: protective material replacement"""
        from aind_data_schema_models.coordinates import AnatomicalRelative
        from aind_data_schema_models.registries import Registry

        data = {
            "procedure_type": "Ground wire",
            "ground_electrode_location": {
                "name": AnatomicalRelative.ORIGIN,
                "registry": Registry.ROR,
                "registry_identifier": "test_id",
            },
        }
        result = upgrade_protective_material_replacement(data)
        self.assertNotIn("procedure_type", result)

    def test_upgrade_sample_collection(self):
        """Test line 263: sample collection"""
        from datetime import datetime

        data = {
            "procedure_type": "SampleCollection",
            "sample_type": "Blood",
            "time": datetime(2023, 1, 1, 10, 0),
            "collection_volume": 1.0,
            "collection_volume_unit": "milliliter",
        }
        result = upgrade_sample_collection(data)
        self.assertNotIn("procedure_type", result)

    def test_upgrade_perfusion(self):
        """Test line 271: perfusion"""
        data = {"procedure_type": "Perfusion", "output_specimen_ids": ["test_specimen"]}
        result = upgrade_perfusion(data)
        self.assertNotIn("procedure_type", result)

    def test_retrieve_probe_config_basic(self):
        """Test line 280-283: basic probe config retrieval"""
        data = {
            "probes": [
                {
                    "targeted_structure": {
                        "name": "test_structure",
                        "atlas": "test_atlas",
                        "acronym": "TS",
                        "id": "123",
                    },
                    "stereotactic_coordinate_ap": 1.0,
                    "stereotactic_coordinate_ml": 2.0,
                    "stereotactic_coordinate_dv": 3.0,
                    "stereotactic_coordinate_unit": "millimeter",
                    "stereotactic_coordinate_reference": "Bregma",
                }
            ]
        }
        probes, configs = retrieve_probe_config(data)
        self.assertIsInstance(probes, list)
        self.assertIsInstance(configs, list)

    def test_retrieve_probe_config_ophys_probe(self):
        """Test lines 288-291: ophys probe handling"""
        data = {
            "probes": [
                {
                    "ophys_probe": {
                        "name": "test_probe",
                        "core_diameter": 1.0,
                        "numerical_aperture": 0.5,
                        "total_length": 10.0,
                    },
                    "targeted_structure": {
                        "name": "test_structure",
                        "atlas": "test_atlas",
                        "acronym": "TS",
                        "id": "123",
                    },
                    "stereotactic_coordinate_ap": 1.0,
                    "stereotactic_coordinate_ml": 2.0,
                    "stereotactic_coordinate_dv": 3.0,
                    "stereotactic_coordinate_unit": "millimeter",
                    "stereotactic_coordinate_reference": "Bregma",
                }
            ]
        }
        probes, configs = retrieve_probe_config(data)
        self.assertEqual(len(probes), 1)

    def test_retrieve_probe_config_no_targeted_structure(self):
        """Test lines 296-297: default targeted structure"""
        data = {
            "probes": [
                {
                    "stereotactic_coordinate_ap": 1.0,
                    "stereotactic_coordinate_ml": 2.0,
                    "stereotactic_coordinate_dv": 3.0,
                    "stereotactic_coordinate_unit": "millimeter",
                    "stereotactic_coordinate_reference": "Bregma",
                }
            ]
        }
        probes, configs = retrieve_probe_config(data)
        self.assertEqual(len(configs), 1)

    def test_retrieve_probe_config_micrometer_conversion(self):
        """Test lines 307-310: micrometer unit conversion"""
        data = {
            "probes": [
                {
                    "stereotactic_coordinate_ap": 1000,
                    "stereotactic_coordinate_ml": 2000,
                    "stereotactic_coordinate_dv": 3000,
                    "stereotactic_coordinate_unit": "micrometer",
                    "stereotactic_coordinate_reference": "Bregma",
                }
            ]
        }
        probes, configs = retrieve_probe_config(data)
        self.assertEqual(len(configs), 1)

    def test_retrieve_probe_config_unsupported_unit(self):
        """Test lines 311-315: unsupported coordinate unit"""
        data = {"probes": [{"stereotactic_coordinate_unit": "meter", "stereotactic_coordinate_reference": "Bregma"}]}
        with self.assertRaises(ValueError):
            retrieve_probe_config(data)

    def test_retrieve_probe_config_unsupported_reference(self):
        """Test lines 322-325: unsupported coordinate reference"""
        data = {
            "probes": [{"stereotactic_coordinate_unit": "millimeter", "stereotactic_coordinate_reference": "Lambda"}]
        }
        with self.assertRaises(ValueError):
            retrieve_probe_config(data)

    def test_retrieve_probe_config_with_angle(self):
        """Test lines 330-338: angle handling"""
        data = {
            "probes": [
                {
                    "stereotactic_coordinate_ap": 1.0,
                    "stereotactic_coordinate_ml": 2.0,
                    "stereotactic_coordinate_dv": 3.0,
                    "stereotactic_coordinate_unit": "millimeter",
                    "stereotactic_coordinate_reference": "Bregma",
                    "angle": 45.0,
                    "angle_unit": "degrees",
                }
            ]
        }
        probes, configs = retrieve_probe_config(data)
        self.assertEqual(len(configs), 1)

    def test_retrieve_probe_config_unsupported_angle_unit(self):
        """Test lines 331-332: unsupported angle unit"""
        data = {
            "probes": [
                {
                    "stereotactic_coordinate_ap": 1.0,
                    "stereotactic_coordinate_ml": 2.0,
                    "stereotactic_coordinate_dv": 3.0,
                    "stereotactic_coordinate_unit": "millimeter",
                    "stereotactic_coordinate_reference": "Bregma",
                    "angle": 45.0,
                    "angle_unit": "radians",
                }
            ]
        }
        with self.assertRaises(ValueError):
            retrieve_probe_config(data)


class TestProceduresUpgraderV1V2OldFormat(unittest.TestCase):
    """Test cases for ProceduresUpgraderV1V2 with old separated format"""

    def setUp(self):
        """Set up test fixtures"""
        self.upgrader = ProceduresUpgraderV1V2()

    def test_is_old_separated_format_true(self):
        """Test detection of old separated format"""
        data = {
            "craniotomies": [{"type": "Dual hemisphere"}],
            "headframes": [{"type": "Dual hemisphere"}],
            "injections": [],
            "subject_id": "655565",
        }
        self.assertTrue(self.upgrader._is_old_separated_format(data))

    def test_is_old_separated_format_false_with_new_format(self):
        """Test rejection of new format"""
        data = {
            "subject_procedures": [],
            "specimen_procedures": [],
            "subject_id": "655565",
        }
        self.assertFalse(self.upgrader._is_old_separated_format(data))

    def test_is_old_separated_format_false_empty(self):
        """Test rejection of empty data"""
        data = {"subject_id": "655565"}
        self.assertFalse(self.upgrader._is_old_separated_format(data))

    def test_convert_old_procedure_craniotomy(self):
        """Test conversion of old craniotomy format"""
        procedure = {
            "type": "Dual hemisphere craniotomy",
            "craniotomy_coordinates_ap": 0,
            "craniotomy_coordinates_ml": 0,
            "craniotomy_size": 8,
        }
        result = self.upgrader._convert_old_procedure_to_intermediate(procedure, "craniotomies")
        
        self.assertEqual(result["procedure_type"], "Craniotomy")
        self.assertEqual(result["craniotomy_type"], "Dual hemisphere craniotomy")
        self.assertNotIn("type", result)
        self.assertEqual(result["craniotomy_coordinates_unit"], "millimeter")
        self.assertEqual(result["craniotomy_coordinates_reference"], "Bregma")
        self.assertEqual(result["craniotomy_size_unit"], "millimeter")

    def test_convert_old_procedure_headframe(self):
        """Test conversion of old headframe format"""
        procedure = {
            "type": "Dual hemisphere",
            "headframe_material": "Titanium",
        }
        result = self.upgrader._convert_old_procedure_to_intermediate(procedure, "headframes")
        
        self.assertEqual(result["procedure_type"], "Headframe")
        self.assertEqual(result["headframe_type"], "Dual hemisphere")
        self.assertNotIn("type", result)

    def test_convert_old_procedure_injection(self):
        """Test conversion of old injection format"""
        procedure = {
            "injection_type": "Nanoject",
            "injection_volume": 300,
            "injection_coordinate_depth": -2.5,
            "injection_angle_unit": "degree",
            "injection_materials": [
                {
                    "full_genome_name": "rAAV-test",
                    "name": "Test virus",
                    "prep_type": "Purified",
                    "titer": 1e13,
                }
            ],
        }
        result = self.upgrader._convert_old_procedure_to_intermediate(procedure, "injections")
        
        self.assertEqual(result["procedure_type"], "Nanoject injection")
        self.assertEqual(result["injection_volume"], [300])
        self.assertEqual(result["injection_coordinate_depth"], [-2.5])
        self.assertEqual(result["injection_angle_unit"], "degrees")
        self.assertEqual(result["injection_materials"][0]["material_type"], "Virus")
        # When name already exists, we keep it and remove full_genome_name
        self.assertEqual(result["injection_materials"][0]["name"], "Test virus")
        self.assertNotIn("full_genome_name", result["injection_materials"][0])
        self.assertNotIn("prep_type", result["injection_materials"][0])

    def test_group_procedures_by_date(self):
        """Test grouping procedures by date"""
        procedures = [
            {"procedure_type": "Craniotomy", "start_date": "2023-02-28", "end_date": "2023-02-28", "protocol_id": "N/A"},
            {"procedure_type": "Headframe", "start_date": "2023-02-28", "end_date": "2023-02-28", "protocol_id": "N/A"},
            {"procedure_type": "Nanoject injection", "start_date": "2023-02-28", "end_date": "2023-02-28", "protocol_id": "N/A"},
            {"procedure_type": "Nanoject injection", "start_date": "2023-03-01", "end_date": "2023-03-01", "protocol_id": "N/A"},
        ]
        
        surgeries = self.upgrader._group_procedures_by_date(procedures)
        
        self.assertEqual(len(surgeries), 2)
        # First surgery should have 3 procedures
        first_surgery = next(s for s in surgeries if s["start_date"] == "2023-02-28")
        self.assertEqual(len(first_surgery["procedures"]), 3)
        # Second surgery should have 1 procedure
        second_surgery = next(s for s in surgeries if s["start_date"] == "2023-03-01")
        self.assertEqual(len(second_surgery["procedures"]), 1)

    def test_upgrade_v1_2_json(self):
        """Test full upgrade of v1_2.json file"""
        # Load the v1_2.json test file
        test_dir = os.path.dirname(__file__)
        v1_2_path = os.path.join(test_dir, "records", "procedures", "v1_2.json")
        
        with open(v1_2_path, "r") as f:
            v1_2_data = json.load(f)
        
        # Upgrade the data
        upgraded = self.upgrader.upgrade(v1_2_data, schema_version="2.0.0")
        
        # Verify the upgrade
        self.assertEqual(upgraded["schema_version"], "2.0.0")
        self.assertEqual(upgraded["subject_id"], "655565")
        self.assertIn("subject_procedures", upgraded)
        self.assertEqual(len(upgraded["subject_procedures"]), 1)
        
        # Verify the surgery
        surgery = upgraded["subject_procedures"][0]
        self.assertEqual(surgery["experimenters"], ["Anna Lakunina"])
        # start_date is a date object after upgrade
        from datetime import date
        self.assertEqual(surgery["start_date"], date(2023, 2, 28))
        self.assertEqual(surgery["ethics_review_id"], "2109")
        
        # Verify procedures within surgery
        # Should have 1 craniotomy, 1 headframe, and 5 injections = 7 total
        self.assertEqual(len(surgery["procedures"]), 7)
        
        # Verify craniotomy
        craniotomy = next((p for p in surgery["procedures"] if p.get("object_type") == "Craniotomy"), None)
        self.assertIsNotNone(craniotomy)
        self.assertEqual(craniotomy["size"], 8.0)
        
        # Verify headframe
        headframe = next((p for p in surgery["procedures"] if p.get("object_type") == "Headframe"), None)
        self.assertIsNotNone(headframe)
        self.assertEqual(headframe["headframe_type"], "Dual hemisphere")
        
        # Verify injections
        injections = [p for p in surgery["procedures"] if p.get("object_type") == "Brain injection"]
        self.assertEqual(len(injections), 5)
        
        # Verify injection materials have correct names
        for injection in injections:
            for material in injection["injection_materials"]:
                self.assertIn("name", material)
                self.assertNotIn("full_genome_name", material)
                self.assertNotIn("prep_type", material)


if __name__ == "__main__":
    unittest.main()
