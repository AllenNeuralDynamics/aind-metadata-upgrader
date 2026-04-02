"""Unit tests for procedures v1v2_injections module"""

import unittest
from aind_data_schema.components.injection_procedures import Injection
from aind_data_schema_models.mouse_anatomy import InjectionTargets
from aind_metadata_upgrader.procedures.v1v2_injections import upgrade_intraperitoneal_injection


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


if __name__ == "__main__":
    unittest.main()
