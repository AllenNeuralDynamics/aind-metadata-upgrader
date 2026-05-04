"""Tests for v1v2_metadata_utils ecephys ID mismatch handling"""

import unittest
from datetime import datetime

from aind_metadata_upgrader.utils.v1v2_metadata_utils import repair_instrument_id_mismatch, repair_acquisition_timezone


def _iso(v):
    """Normalise a string or datetime to an ISO string for assertion comparisons."""
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _make_data(instrument_id, acquisition_id):
    """Helper to create test data dicts with specified instrument and acquisition IDs"""
    return {
        "instrument": {"instrument_id": instrument_id},
        "acquisition": {"instrument_id": acquisition_id},
    }


class TestHandleEcephysIdMismatch(unittest.TestCase):
    """Tests for repair_instrument_id_mismatch"""

    def test_already_matching(self):
        """No change when IDs already match"""
        data = _make_data("323_EPHYS2_RF_2024-12-22_01", "323_EPHYS2_RF_2024-12-22_01")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")

    def test_date_format_difference_yyyymmdd_vs_yyyy_mm_dd(self):
        """Rig YYYYMMDD vs session YYYY-MM-DD — normalise to session format"""
        # Row: 323_EPHYS2_RF_20241222_01, 323_EPHYS2_RF_2024-12-22_01
        data = _make_data("323_EPHYS2_RF_20241222_01", "323_EPHYS2_RF_2024-12-22_01")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")

    def test_date_format_difference_vr_rig(self):
        """Rig YYYYMMDD vs session YYYY-MM-DD for VR rig"""
        # Row: 322_EPHYS5_VR_20251028_01, 322_EPHYS5_VR_2025-10-28_01
        data = _make_data("322_EPHYS5_VR_20251028_01", "322_EPHYS5_VR_2025-10-28_01")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "322_EPHYS5_VR_2025-10-28_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "322_EPHYS5_VR_2025-10-28_01")

    def test_rig_date_more_recent_copy_rig_to_acquisition(self):
        """Rig has more recent date — copy rig ID into acquisition"""
        # Row: 327_NP2_240416, 327_NP2_240401
        data = _make_data("327_NP2_240416", "327_NP2_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "327_NP2_240416")
        self.assertEqual(result["acquisition"]["instrument_id"], "327_NP2_240416")

    def test_rig_date_more_recent_8digit(self):
        """Rig has more recent 8-digit date — copy rig ID into acquisition"""
        # Row: 342_NP3_240408, 342_NP3_240401
        data = _make_data("342_NP3_20240408", "342_NP3_20240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_20240408")

    def test_session_date_more_recent_uses_instrument(self):
        """Session has more recent date — use instrument ID (Rule 9 always prefers instrument)"""
        # Row: 155_Chronic1_20251107, 155_Chronic1_20251201
        data = _make_data("155_Chronic1_20251107", "155_Chronic1_20251201")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "155_Chronic1_20251107")
        self.assertEqual(result["acquisition"]["instrument_id"], "155_Chronic1_20251107")

    def test_punctuation_diff_same_date_prefer_rig(self):
        """NP.3 vs NP3 with equal date — dot normalisation uses acquisition form (Rule 4)"""
        # Row: 342_NP.3_20241111, 342_NP3_20241111
        data = _make_data("342_NP.3_20241111", "342_NP3_20241111")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_20241111")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_20241111")

    def test_different_room_prefix_prefer_rig(self):
        """Different room prefix (342_ vs unknown_) — prefer rig"""
        # Row: 342_NP3_240906, unknown_NP3_240401
        data = _make_data("342_NP3_240906", "unknown_NP3_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240906")

    def test_bad_instrument_id_overwritten_by_acquisition(self):
        """Known-bad instrument IDs are overwritten by the acquisition value"""
        data = _make_data("322_EPHYS5_Ephys5", "ND_Ephys.5")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "ND_Ephys.5")
        self.assertEqual(result["acquisition"]["instrument_id"], "ND_Ephys.5")

    def test_missing_instrument_id_returns_unchanged(self):
        """Missing instrument_id — return data unchanged"""
        data = _make_data(None, "327_NP2_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertIsNone(result["instrument"]["instrument_id"])

    def test_missing_acquisition_id_returns_unchanged(self):
        """Missing acquisition instrument_id — return data unchanged"""
        data = _make_data("342_NP3_240906", None)
        result = repair_instrument_id_mismatch(data)
        self.assertIsNone(result["acquisition"]["instrument_id"])


class TestRepairAcquisitionTimezone(unittest.TestCase):
    """Tests for repair_acquisition_timezone"""

    def _make_acq(self, start, end, stream_starts=None, stream_ends=None, epoch_starts=None, epoch_ends=None):
        streams = []
        for i, ss in enumerate(stream_starts or []):
            stream = {"stream_start_time": ss}
            if stream_ends and i < len(stream_ends):
                stream["stream_end_time"] = stream_ends[i]
            streams.append(stream)
        epochs = []
        for i, es in enumerate(epoch_starts or []):
            epoch = {"stimulus_start_time": es}
            if epoch_ends and i < len(epoch_ends):
                epoch["stimulus_end_time"] = epoch_ends[i]
            epochs.append(epoch)
        return {
            "acquisition": {
                "acquisition_start_time": start,
                "acquisition_end_time": end,
                "data_streams": streams,
                "stimulus_epochs": epochs,
            }
        }

    def test_no_change_when_start_is_utc(self):
        """No change when acquisition_start_time is UTC — values remain as original strings"""
        data = self._make_acq(
            "2023-08-31T12:33:31Z",
            "2023-08-31T14:29:44Z",
            ["2023-08-31T12:33:31Z"],
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(result["acquisition"]["acquisition_end_time"], "2023-08-31T14:29:44Z")
        self.assertEqual(result["acquisition"]["data_streams"][0]["stream_start_time"], "2023-08-31T12:33:31Z")

    def test_fix_applied_when_reinterpretation_is_valid(self):
        """Fix is applied when reinterpreting UTC times makes everything fit within acquisition bounds"""
        data = self._make_acq(
            "2023-08-31T12:33:31-07:00",
            "2023-08-31T14:29:44.718331Z",
            ["2023-08-31T12:33:31.218331Z"],
            ["2023-08-31T14:29:44.497900-07:00"],
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(_iso(result["acquisition"]["acquisition_end_time"]), "2023-08-31T14:29:44.718331-07:00")
        self.assertEqual(_iso(result["acquisition"]["data_streams"][0]["stream_start_time"]), "2023-08-31T12:33:31.218331-07:00")
        # stream_end_time was already -07:00, should be unchanged (not UTC → stays as original type)
        self.assertEqual(_iso(result["acquisition"]["data_streams"][0]["stream_end_time"]), "2023-08-31T14:29:44.497900-07:00")

    def test_no_fix_when_reinterpretation_invalid(self):
        """No fix applied when reinterpreting UTC times would still violate containment"""
        data = self._make_acq(
            "2023-08-31T13:00:00-07:00",
            "2023-08-31T14:29:44Z",
            ["2023-08-31T12:00:00Z"],  # reinterpreted → 12:00-07:00 < 13:00-07:00: invalid
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(result["acquisition"]["acquisition_end_time"], "2023-08-31T14:29:44Z")
        self.assertEqual(result["acquisition"]["data_streams"][0]["stream_start_time"], "2023-08-31T12:00:00Z")

    def test_no_change_when_end_already_has_tz(self):
        """No change to end time when it already has a non-UTC timezone"""
        data = self._make_acq(
            "2023-08-31T12:33:31-07:00",
            "2023-08-31T14:29:44-07:00",
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(_iso(result["acquisition"]["acquisition_end_time"]), "2023-08-31T14:29:44-07:00")

    def test_no_acquisition_key(self):
        """No crash when acquisition key is missing"""
        data = {"subject": {}}
        result = repair_acquisition_timezone(data)
        self.assertNotIn("acquisition", result)

    def test_multiple_streams_partially_utc(self):
        """Only UTC stream times are reinterpreted; non-UTC ones are left alone when valid"""
        data = self._make_acq(
            "2023-08-31T12:33:31-07:00",
            "2023-08-31T14:29:44Z",
            ["2023-08-31T12:33:31Z", "2023-08-31T13:00:00-07:00"],
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(_iso(result["acquisition"]["data_streams"][0]["stream_start_time"]), "2023-08-31T12:33:31-07:00")
        self.assertEqual(_iso(result["acquisition"]["data_streams"][1]["stream_start_time"]), "2023-08-31T13:00:00-07:00")

    def test_stimulus_epochs_patched_when_valid(self):
        """Stimulus epoch times are also patched when the fix is valid"""
        data = self._make_acq(
            "2023-08-31T12:33:31-07:00",
            "2023-08-31T14:29:44Z",
            [],
            [],
            ["2023-08-31T12:34:31Z"],
            ["2023-08-31T12:48:51Z"],
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(_iso(result["acquisition"]["stimulus_epochs"][0]["stimulus_start_time"]), "2023-08-31T12:34:31-07:00")
        self.assertEqual(_iso(result["acquisition"]["stimulus_epochs"][0]["stimulus_end_time"]), "2023-08-31T12:48:51-07:00")

    def test_no_fix_when_epoch_outside_bounds(self):
        """No fix applied when a stimulus epoch would fall outside acquisition bounds after reinterpretation"""
        data = self._make_acq(
            "2023-08-31T12:33:31-07:00",
            "2023-08-31T14:29:44Z",
            [],
            [],
            ["2023-08-31T12:34:31Z"],
            ["2023-08-31T15:00:00Z"],  # 15:00-07:00 > 14:29-07:00: invalid
        )
        result = repair_acquisition_timezone(data)
        self.assertEqual(result["acquisition"]["stimulus_epochs"][0]["stimulus_end_time"], "2023-08-31T15:00:00Z")

    def test_fix_works_with_datetime_objects(self):
        """Works when values are already datetime objects (as from model_dump())"""
        from datetime import timezone, timedelta
        tz_minus7 = timezone(timedelta(hours=-7))
        utc = timezone.utc
        data = {
            "acquisition": {
                "acquisition_start_time": datetime(2023, 8, 31, 12, 33, 31, tzinfo=tz_minus7),
                "acquisition_end_time": datetime(2023, 8, 31, 14, 29, 44, tzinfo=utc),
                "data_streams": [{"stream_start_time": datetime(2023, 8, 31, 12, 33, 31, tzinfo=utc)}],
                "stimulus_epochs": [],
            }
        }
        result = repair_acquisition_timezone(data)
        self.assertEqual(_iso(result["acquisition"]["acquisition_end_time"]), "2023-08-31T14:29:44-07:00")
        self.assertEqual(_iso(result["acquisition"]["data_streams"][0]["stream_start_time"]), "2023-08-31T12:33:31-07:00")


if __name__ == "__main__":
    unittest.main()
