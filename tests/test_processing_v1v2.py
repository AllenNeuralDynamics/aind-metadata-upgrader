"""Tests for processing v1v2 upgrade functionality"""

import unittest

from aind_metadata_upgrader.processing.v1v2 import ProcessingV1V2


class TestProcessingV1V2(unittest.TestCase):
    """Test the ProcessingV1V2 class"""

    def setUp(self):
        """Setup"""
        self.upgrader = ProcessingV1V2()

    def test_upgrade_with_invalid_data_type(self):
        """Test upgrade method with non-dict data - covers line 93"""
        with self.assertRaises(ValueError) as context:
            self.upgrader.upgrade("not a dict", "2.0.78")  # type: ignore
        self.assertEqual(str(context.exception), "Data must be a dictionary")

    def test_convert_v1_process_to_v2_with_analyst_name(self):
        """Test _convert_v1_process_to_v2 with analyst_full_name - covers lines 44-48"""
        process_data = {
            "name": "Analysis",
            "analyst_full_name": "Test Analyst",
            "code_url": "http://example.com",
            "code_version": "1.0",
            "start_date_time": "2024-01-01T10:00:00Z",
            "end_date_time": "2024-01-01T12:00:00Z",
            "output_location": "/path/to/output",
            "notes": "Test notes",
        }
        result = self.upgrader._convert_v1_process_to_v2(process_data, "Analysis")
        self.assertEqual(result["experimenters"], ["Test Analyst"])

    def test_convert_v1_process_to_v2_other_with_no_notes(self):
        """Test _convert_v1_process_to_v2 with name 'Other' and no notes - covers line 59"""
        process_data = {
            "name": "Other",
            "code_url": "http://example.com",
            "code_version": "1.0",
            "start_date_time": "2024-01-01T10:00:00Z",
            "end_date_time": "2024-01-01T12:00:00Z",
        }
        result = self.upgrader._convert_v1_process_to_v2(process_data, "Processing")
        self.assertEqual(result["notes"], "(v1v2 upgrade) Process type is unknown, no notes were provided.")

    def test_upgrade_with_analyses_duplicate_names(self):
        """Test upgrade with analyses having duplicate names - covers lines 126-138"""

        data = {
            "processing_pipeline": {
                "data_processes": [
                    {
                        "name": "Analysis",
                        "code_url": "http://example.com",
                        "code_version": "1.0",
                        "start_date_time": "2024-01-01T10:00:00Z",
                        "end_date_time": "2024-01-01T12:00:00Z",
                    }
                ],
                "processor_full_name": "Test Processor",
            },
            "analyses": [
                {
                    "name": "Analysis",
                    "code_url": "http://example.com",
                    "code_version": "1.0",
                    "start_date_time": "2024-01-01T10:00:00Z",
                    "end_date_time": "2024-01-01T12:00:00Z",
                },
                {
                    "name": "Analysis",
                    "code_url": "http://example.com",
                    "code_version": "1.0",
                    "start_date_time": "2024-01-01T10:00:00Z",
                    "end_date_time": "2024-01-01T12:00:00Z",
                },
            ],
        }
        result = self.upgrader.upgrade(data, "2.0.78")

        # Check that duplicate names are handled
        process_names = [proc["name"] for proc in result["data_processes"]]
        self.assertIn("Analysis_1", process_names)  # First processing process
        self.assertIn("Analysis_2", process_names)  # First analysis (duplicate resolved)
        self.assertIn("Analysis_3", process_names)  # Second analysis (duplicate resolved)

    def test_upgrade_with_analyses_complex_duplicate_names(self):
        """Test upgrade with analyses having complex duplicate names - covers lines 132-135"""

        # Create a scenario where processing creates "Analysis_1", "Analysis_2",
        # and then analyses has "Analysis" which should become "Analysis_3"
        # and another "Analysis" which should check if "Analysis_1" is in seen_names
        data = {
            "processing_pipeline": {
                "data_processes": [
                    {
                        "name": "Analysis",
                        "code_url": "http://example.com",
                        "code_version": "1.0",
                        "start_date_time": "2024-01-01T10:00:00Z",
                        "end_date_time": "2024-01-01T12:00:00Z",
                    },
                    {
                        "name": "Analysis",
                        "code_url": "http://example.com",
                        "code_version": "1.0",
                        "start_date_time": "2024-01-01T10:00:00Z",
                        "end_date_time": "2024-01-01T12:00:00Z",
                    },
                ],
                "processor_full_name": "Test Processor",
            },
            "analyses": [
                {
                    "name": "Analysis",  # This will become Analysis_3
                    "code_url": "http://example.com",
                    "code_version": "1.0",
                    "start_date_time": "2024-01-01T10:00:00Z",
                    "end_date_time": "2024-01-01T12:00:00Z",
                },
                {
                    "name": "Analysis",  # This will try Analysis_1, Analysis_2, Analysis_3, finally use Analysis_4
                    "code_url": "http://example.com",
                    "code_version": "1.0",
                    "start_date_time": "2024-01-01T10:00:00Z",
                    "end_date_time": "2024-01-01T12:00:00Z",
                },
            ],
        }
        result = self.upgrader.upgrade(data, "2.0.78")

        # Check that the while loop incremented properly when Analysis_1, Analysis_2, Analysis_3 were already seen
        process_names = [proc["name"] for proc in result["data_processes"]]
        self.assertIn("Analysis_1", process_names)  # First processing process
        self.assertIn("Analysis_2", process_names)  # Second processing process
        self.assertIn("Analysis_3", process_names)  # First analysis
        self.assertIn("Analysis_4", process_names)  # Second analysis (had to skip Analysis_1, 2, 3)


if __name__ == "__main__":
    unittest.main()
