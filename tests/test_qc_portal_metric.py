"""Tests for the QC Portal metric upgrade functions"""

import unittest
from aind_metadata_upgrader.quality_control.v1v2 import upgrade_qcportal_metric_value


class TestQCPortalMetricUpgrade(unittest.TestCase):
    """Test cases for QC Portal metric upgrade functions"""

    def test_upgrade_qcportal_metric_none(self):
        """Test handling of None input"""
        self.assertIsNone(upgrade_qcportal_metric_value(None))

    def test_upgrade_qcportal_metric_empty(self):
        """Test handling of empty dict"""
        self.assertEqual(upgrade_qcportal_metric_value({}), {})

    def test_upgrade_qcportal_metric_no_type(self):
        """Test handling of dict without type"""
        data = {"value": "test"}
        self.assertEqual(upgrade_qcportal_metric_value(data), data)

    def test_upgrade_qcportal_metric_dropdown_valid(self):
        """Test upgrading a valid dropdown metric"""
        data = {"type": "dropdown", "options": ["a", "b", "c"], "value": "b"}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, data)

    def test_upgrade_qcportal_metric_dropdown_invalid(self):
        """Test upgrading a dropdown metric with invalid value"""
        data = {"type": "dropdown", "options": ["a", "b", "c"], "value": "d"}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, {"type": "dropdown", "options": ["a", "b", "c"], "value": None})

    def test_upgrade_qcportal_metric_checkbox_valid_list(self):
        """Test upgrading a valid checkbox metric with list value"""
        data = {"type": "checkbox", "options": ["a", "b", "c"], "value": ["a", "b"]}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, data)

    def test_upgrade_qcportal_metric_checkbox_single_to_list(self):
        """Test upgrading a checkbox metric with single value"""
        data = {"type": "checkbox", "options": ["a", "b", "c"], "value": "a"}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, {"type": "checkbox", "options": ["a", "b", "c"], "value": ["a"]})

    def test_upgrade_qcportal_metric_checkbox_invalid(self):
        """Test upgrading a checkbox metric with invalid values"""
        data = {"type": "checkbox", "options": ["a", "b", "c"], "value": ["d", "e"]}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, {"type": "checkbox", "options": ["a", "b", "c"], "value": []})

    def test_upgrade_qcportal_metric_checkbox_mixed_invalid(self):
        """Test upgrading a checkbox metric with mix of valid and invalid values"""
        data = {"type": "checkbox", "options": ["a", "b", "c"], "value": ["a", "d"]}
        result = upgrade_qcportal_metric_value(data)
        self.assertEqual(result, {"type": "checkbox", "options": ["a", "b", "c"], "value": ["a"]})


if __name__ == "__main__":
    unittest.main()
