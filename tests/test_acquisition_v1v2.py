"""Tests for acquisition v1v2 upgrade functionality"""

import unittest
from unittest.mock import patch

from aind_metadata_upgrader.acquisition.v1v2 import AcquisitionV1V2


class TestAcquisitionV1V2(unittest.TestCase):
    """Test the AcquisitionV1V2 class"""

    def setUp(self):
        """Setup"""
        self.upgrader = AcquisitionV1V2()

    def test_upgrade_with_invalid_data_type(self):
        """Test upgrade method with non-dict data - covers line 67"""
        with self.assertRaises(ValueError) as context:
            self.upgrader.upgrade("not a dict", "2.0.34", metadata={})  # type: ignore
        self.assertEqual(str(context.exception), "Data must be a dictionary")

    def test_determine_acquisition_type_with_session_type(self):
        """Test _determine_acquisition_type when session_type exists - covers line 54"""
        data = {"session_type": "Custom Session Type"}
        result = self.upgrader._determine_acquisition_type(data)
        self.assertEqual(result, "Custom Session Type")

    def test_determine_acquisition_type_with_tiles_no_session_type(self):
        """Test _determine_acquisition_type when tiles exist but no session_type - covers line 61"""
        data = {"tiles": [{"some": "tile"}]}
        result = self.upgrader._determine_acquisition_type(data)
        self.assertEqual(result, "Imaging session")

    def test_upgrade_with_string_datetime(self):
        """Test upgrade with string datetime - covers line 94"""
        # Mock the upgrade_tiles_to_data_stream function since it's external
        with patch("aind_metadata_upgrader.acquisition.v1v2.upgrade_tiles_to_data_stream") as mock_upgrade_tiles:
            mock_upgrade_tiles.return_value = [{"active_devices": []}]

            # Mock upgrade_calibration and upgrade_reagent since they're external
            with patch("aind_metadata_upgrader.acquisition.v1v2.upgrade_calibration") as mock_upgrade_cal:
                mock_upgrade_cal.return_value = {}

                data = {
                    "subject_id": "test_subject",
                    "session_start_time": "2024-01-01T10:00:00",  # String datetime
                    "session_end_time": "2024-01-01T11:00:00",  # String datetime
                    "calibrations": [],
                    "maintenance": [],
                }

                result = self.upgrader.upgrade(data, "2.0.34", metadata={})
                self.assertIsNotNone(result)
                self.assertEqual(result["subject_id"], "test_subject")

    def test_upgrade_without_session_times(self):
        """Test upgrade without session times - covers line 140"""
        data = {
            "subject_id": "test_subject",
            # No session_start_time or session_end_time
        }

        with self.assertRaises(NotImplementedError):
            self.upgrader.upgrade(data, "2.0.34", metadata={})


if __name__ == "__main__":
    unittest.main()
