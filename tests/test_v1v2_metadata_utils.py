"""Tests for v1v2_metadata_utils ecephys ID mismatch handling"""

import unittest

from aind_metadata_upgrader.utils.v1v2_metadata_utils import _handle_ecephys_id_mismatch


def _make_data(instrument_id, acquisition_id):
    """Helper to create test data dicts with specified instrument and acquisition IDs"""
    return {
        "instrument": {"instrument_id": instrument_id},
        "acquisition": {"instrument_id": acquisition_id},
    }


class TestHandleEcephysIdMismatch(unittest.TestCase):
    """Tests for _handle_ecephys_id_mismatch"""

    def test_already_matching(self):
        """No change when IDs already match"""
        data = _make_data("323_EPHYS2_RF_2024-12-22_01", "323_EPHYS2_RF_2024-12-22_01")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")

    def test_date_format_difference_yyyymmdd_vs_yyyy_mm_dd(self):
        """Rig YYYYMMDD vs session YYYY-MM-DD — normalise to session format"""
        # Row: 323_EPHYS2_RF_20241222_01, 323_EPHYS2_RF_2024-12-22_01
        data = _make_data("323_EPHYS2_RF_20241222_01", "323_EPHYS2_RF_2024-12-22_01")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")

    def test_date_format_difference_vr_rig(self):
        """Rig YYYYMMDD vs session YYYY-MM-DD for VR rig"""
        # Row: 322_EPHYS5_VR_20251028_01, 322_EPHYS5_VR_2025-10-28_01
        data = _make_data("322_EPHYS5_VR_20251028_01", "322_EPHYS5_VR_2025-10-28_01")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "322_EPHYS5_VR_2025-10-28_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "322_EPHYS5_VR_2025-10-28_01")

    def test_rig_date_more_recent_copy_rig_to_acquisition(self):
        """Rig has more recent date — copy rig ID into acquisition"""
        # Row: 327_NP2_240416, 327_NP2_240401
        data = _make_data("327_NP2_240416", "327_NP2_240401")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "327_NP2_240416")
        self.assertEqual(result["acquisition"]["instrument_id"], "327_NP2_240416")

    def test_rig_date_more_recent_8digit(self):
        """Rig has more recent 8-digit date — copy rig ID into acquisition"""
        # Row: 342_NP3_240408, 342_NP3_240401
        data = _make_data("342_NP3_20240408", "342_NP3_20240401")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_20240408")

    def test_session_date_more_recent_raises(self):
        """Session has more recent date — raise ValueError"""
        # Row: 155_Chronic1_20251107, 155_Chronic1_20251201
        data = _make_data("155_Chronic1_20251107", "155_Chronic1_20251201")
        with self.assertRaises(ValueError) as ctx:
            _handle_ecephys_id_mismatch(data)
        self.assertIn("more recent date", str(ctx.exception))

    def test_punctuation_diff_same_date_prefer_rig(self):
        """NP.3 vs NP3 with equal date — prefer rig, copy into acquisition"""
        # Row: 342_NP.3_20241111, 342_NP3_20241111
        data = _make_data("342_NP.3_20241111", "342_NP3_20241111")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP.3_20241111")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP.3_20241111")

    def test_different_room_prefix_prefer_rig(self):
        """Different room prefix (342_ vs unknown_) — prefer rig"""
        # Row: 342_NP3_240906, unknown_NP3_240401
        data = _make_data("342_NP3_240906", "unknown_NP3_240401")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240906")

    def test_bad_instrument_id_overwritten_by_acquisition(self):
        """Known-bad instrument IDs are overwritten by the acquisition value"""
        data = _make_data("322_EPHYS5_Ephys5", "ND_Ephys.5")
        result = _handle_ecephys_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "ND_Ephys.5")
        self.assertEqual(result["acquisition"]["instrument_id"], "ND_Ephys.5")

    def test_missing_instrument_id_returns_unchanged(self):
        """Missing instrument_id — return data unchanged"""
        data = _make_data(None, "327_NP2_240401")
        result = _handle_ecephys_id_mismatch(data)
        self.assertIsNone(result["instrument"]["instrument_id"])

    def test_missing_acquisition_id_returns_unchanged(self):
        """Missing acquisition instrument_id — return data unchanged"""
        data = _make_data("342_NP3_240906", None)
        result = _handle_ecephys_id_mismatch(data)
        self.assertIsNone(result["acquisition"]["instrument_id"])


if __name__ == "__main__":
    unittest.main()
