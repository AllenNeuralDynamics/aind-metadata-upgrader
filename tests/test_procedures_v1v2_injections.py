"""Unit tests for procedures v1v2_injections module"""

import unittest
from aind_data_schema.components.injection_procedures import Injection
from aind_data_schema_models.mouse_anatomy import InjectionTargets
from aind_metadata_upgrader.procedures.v1v2_injections import (
    upgrade_injection_coordinates,
    upgrade_intraperitoneal_injection,
)


class TestIntraperitonealInjection(unittest.TestCase):
    """Test cases for upgrade_intraperitoneal_injection"""

    def test_upgrade_intraperitoneal_injection(self):
        """Test that a V1 intraperitoneal injection is properly upgraded to a valid Injection object"""
        v1_data = {
            "injection_materials": [
                {
                    "name": "Heparin",
                    "rrid": None,
                    "expiration_date": None,
                    "material_type": "Reagent",
                    "concentration": "1000",
                    "concentration_unit": "u/ml",
                }
            ],
            "recovery_time": None,
            "recovery_time_unit": "minute",
            "injection_duration": None,
            "injection_duration_unit": "minute",
            "instrument_id": None,
            "time": None,
            "injection_volume": None,
            "injection_volume_unit": "microliter",
        }

        result = upgrade_intraperitoneal_injection(v1_data)

        # Validate the result builds a valid Injection object
        injection = Injection(**result)
        self.assertIsNotNone(injection)

        # targeted_structure should be INTRAPERITONEAL
        self.assertEqual(result["targeted_structure"], InjectionTargets.INTRAPERITONEAL.model_dump())

        # Removed fields should not be present
        self.assertNotIn("recovery_time", result)
        self.assertNotIn("recovery_time_unit", result)
        self.assertNotIn("instrument_id", result)
        self.assertNotIn("time", result)
        self.assertNotIn("injection_volume", result)
        self.assertNotIn("injection_volume_unit", result)
        self.assertNotIn("injection_duration", result)
        self.assertNotIn("injection_duration_unit", result)


class TestUpgradeInjectionCoordinatesAngle(unittest.TestCase):
    """Test that the AP angle sign is corrected based on ML hemisphere"""

    def _make_data(self, ml, angle):
        return {
            "injection_coordinate_ml": ml,
            "injection_coordinate_ap": "1.0",
            "injection_coordinate_depth": ["2.0"],
            "injection_coordinate_unit": "millimeter",
            "injection_coordinate_reference": "Bregma",
            "injection_angle": angle,
            "injection_angle_unit": "degrees",
        }

    def _get_ap_angle(self, data):
        result = upgrade_injection_coordinates(data)
        # coordinates[0] is the first depth; [1] is the rotation (after translation)
        rotation = result["coordinates"][0][1]
        return rotation["angles"][0]

    def test_left_hemisphere_angle_is_negative(self):
        """Positive angle with left hemisphere (ml<0) should become negative"""
        data = self._make_data(ml="-1.5", angle="10.0")
        self.assertLess(self._get_ap_angle(data), 0)

    def test_left_hemisphere_negative_angle_stays_negative(self):
        """Already-negative angle with left hemisphere should stay negative"""
        data = self._make_data(ml="-1.5", angle="-10.0")
        self.assertLess(self._get_ap_angle(data), 0)

    def test_right_hemisphere_angle_is_positive(self):
        """Angle with right hemisphere (ml>0) should not be negated"""
        data = self._make_data(ml="1.5", angle="10.0")
        self.assertGreater(self._get_ap_angle(data), 0)

    def test_zero_angle_stays_zero(self):
        """Zero angle should stay zero regardless of hemisphere"""
        data = self._make_data(ml="-1.5", angle="0.0")
        self.assertEqual(self._get_ap_angle(data), 0.0)


if __name__ == "__main__":
    unittest.main()
