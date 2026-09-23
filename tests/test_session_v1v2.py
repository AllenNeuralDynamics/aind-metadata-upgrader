"""Tests for session v1v2 _validate_and_adjust_session_times"""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from aind_metadata_upgrader.session.v1v2 import SessionV1V2


PACIFIC = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")


def dt(year, month, day, hour, minute, second=0, tz=PACIFIC):
    """Helper to create datetimes with default Pacific tz and 0 seconds"""
    return datetime(year, month, day, hour, minute, second, tzinfo=tz)


class TestValidateAndAdjustSessionTimes(unittest.TestCase):
    """Tests for _validate_and_adjust_session_times"""

    def setUp(self):
        """Set up a SessionV1V2 upgrader instance for testing"""
        self.upgrader = SessionV1V2()

    def test_stimulus_epoch_stage_in_use_becomes_curriculum_status(self):
        """Copy stage_in_use from output task parameters to curriculum status"""
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "training stimulus",
            "stimulus_modalities": ["Visual"],
            "output_parameters": {"task_parameters": {"stage_in_use": "STAGE_FINAL"}},
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)

        self.assertEqual(upgraded_epoch["curriculum_status"], "STAGE_FINAL")

    def test_stimulus_epoch_without_stage_in_use_has_no_curriculum_status(self):
        """Missing output task parameters leave curriculum status unset"""
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "training stimulus",
            "stimulus_modalities": ["Visual"],
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)

        self.assertIsNone(upgraded_epoch["curriculum_status"])

    def _call(self, start, end, streams=None, epochs=None, notes=None, fallback_tz=None):
        """Helper to call _validate_and_adjust_session_times with given inputs"""
        return self.upgrader._validate_and_adjust_session_times(
            start, end, streams or [], epochs or [], notes, fallback_tz=fallback_tz
        )

    # --- timezone normalization ---

    def test_both_times_get_pacific_tz_from_naive_strings(self):
        """Naive ISO strings get Pacific tz assigned"""
        start, end, _ = self._call("2025-09-25T10:00:00", "2025-09-25T11:00:00")
        self.assertIsNotNone(start.tzinfo)
        self.assertIsNotNone(end.tzinfo)
        self.assertEqual(start.tzinfo, end.tzinfo)

    def test_end_tz_copied_from_start_when_different_initial_tz(self):
        """If start is Pacific and end is UTC, end gets start's tz"""
        start_str = "2025-09-25T10:00:00-07:00"
        end_str = "2025-09-25T11:00:00+00:00"
        start, end, _ = self._call(start_str, end_str)
        self.assertEqual(start.tzinfo, end.tzinfo)

    def test_end_tz_copied_from_start_after_adjustment_by_utc_stream(self):
        """If end is replaced by a UTC stream end time, it gets astimezone'd back to Pacific"""
        session_start = "2025-09-25T10:00:00-07:00"
        session_end = "2025-09-25T11:00:00-07:00"
        # Stream end is UTC and *later* than session end, so it will replace session_end
        stream_end_utc = dt(2025, 9, 25, 19, 0, tz=UTC)  # 19:00 UTC == 12:00 PDT
        streams = [
            {"stream_start_time": dt(2025, 9, 25, 10, 0, tz=PACIFIC), "stream_end_time": stream_end_utc}
        ]
        start, end, _ = self._call(session_start, session_end, streams=streams)
        self.assertEqual(start.tzinfo, end.tzinfo)
        self.assertNotEqual(str(start.tzinfo), "UTC")
        self.assertNotEqual(str(end.tzinfo), "UTC")

    def test_start_tz_copied_when_replaced_by_utc_stream_start(self):
        """If start is replaced by a UTC stream start time, it gets astimezone'd back to Pacific"""
        # Session start is later than the stream start — stream start should become new session start
        session_start = "2025-09-25T10:30:00-07:00"
        session_end = "2025-09-25T13:00:00-07:00"
        stream_start_utc = dt(2025, 9, 25, 17, 0, tz=UTC)  # 17:00 UTC == 10:00 PDT, before session_start
        streams = [
            {"stream_start_time": stream_start_utc, "stream_end_time": dt(2025, 9, 25, 12, 0, tz=PACIFIC)}
        ]
        start, end, _ = self._call(session_start, session_end, streams=streams)
        # Both should be in the same timezone and not UTC
        self.assertEqual(start.tzinfo, end.tzinfo)
        self.assertNotEqual(str(start.tzinfo), "UTC")
        self.assertNotEqual(str(end.tzinfo), "UTC")

    # --- basic adjustment logic ---

    def test_start_time_adjusted_when_stream_starts_earlier(self):
        """Session start moves earlier when a stream starts before it"""
        session_start = "2025-09-25T10:30:00-07:00"
        session_end = "2025-09-25T13:00:00-07:00"
        streams = [
            {"stream_start_time": dt(2025, 9, 25, 10, 0, tz=PACIFIC),
             "stream_end_time": dt(2025, 9, 25, 12, 0, tz=PACIFIC)}
        ]
        start, end, notes = self._call(session_start, session_end, streams=streams)
        self.assertEqual(start.hour, 10)
        self.assertEqual(start.minute, 0)
        self.assertIn("adjusted", notes)

    def test_end_time_adjusted_when_stream_ends_later(self):
        """Session end moves later when a stream ends after it"""
        session_start = "2025-09-25T10:00:00-07:00"
        session_end = "2025-09-25T11:00:00-07:00"
        streams = [
            {"stream_start_time": dt(2025, 9, 25, 10, 0, tz=PACIFIC),
             "stream_end_time": dt(2025, 9, 25, 12, 0, tz=PACIFIC)}
        ]
        start, end, notes = self._call(session_start, session_end, streams=streams)
        self.assertEqual(end.hour, 12)
        self.assertIn("adjusted", notes)

    def test_inverted_times_are_swapped(self):
        """Start later than end gets swapped"""
        start, end, _ = self._call("2025-09-25T12:00:00-07:00", "2025-09-25T10:00:00-07:00")
        self.assertLessEqual(start, end)

    def test_none_end_time_filled_from_streams(self):
        """None session_end_time is filled from stream end times"""
        session_start = "2025-09-25T10:00:00-07:00"
        streams = [
            {"stream_start_time": dt(2025, 9, 25, 10, 0, tz=PACIFIC),
             "stream_end_time": dt(2025, 9, 25, 12, 0, tz=PACIFIC)}
        ]
        start, end, _ = self._call(session_start, None, streams=streams)
        self.assertIsNotNone(end)
        self.assertEqual(end.hour, 12)

    def test_no_streams_no_adjustment(self):
        """No streams/epochs — times pass through unchanged (except tz normalization)"""
        start, end, notes = self._call("2025-09-25T10:00:00-07:00", "2025-09-25T12:00:00-07:00")
        self.assertEqual(start.hour, 10)
        self.assertEqual(end.hour, 12)
        self.assertIsNone(notes)


class TestUpgradeStimulusEpochSoftware(unittest.TestCase):
    """Tests for stimulus epoch software conversion."""

    def setUp(self):
        """Create the session upgrader used by each test."""
        self.upgrader = SessionV1V2()

    def test_software_without_script_populates_code_fields(self):
        """Map software metadata to Code fields when script is absent."""
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "training stimulus",
            "stimulus_modalities": ["Visual"],
            "script": None,
            "software": [
                {
                    "name": "behavior-task",
                    "version": "1.2.3",
                    "url": "https://example.test/behavior-task",
                }
            ],
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)
        code = upgraded_epoch["code"]

        self.assertEqual(code["name"], "behavior-task")
        self.assertEqual(code["version"], "1.2.3")
        self.assertIsNone(code["commit_hash"])
        self.assertEqual(code["url"], "https://example.test/behavior-task")
        self.assertIsNone(code["core_dependency"])

    def test_software_version_text_populates_code_version_and_commit_hash(self):
        """Parse dynamic-foraging-task version and commit from its legacy string."""
        commit_hash = "94823a7969e2f423cdb2eab12d55023efe4c5156"
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "training stimulus",
            "stimulus_modalities": ["Visual"],
            "script": None,
            "software": [
                {
                    "name": "dynamic-foraging-task",
                    "version": (
                        f"behavior branch:main commit ID:{commit_hash} version:1.6.33; "
                        f"metadata branch:main commit ID:{commit_hash} version:1.6.33"
                    ),
                }
            ],
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)
        code = upgraded_epoch["code"]

        self.assertEqual(code["name"], "dynamic-foraging-task")
        self.assertEqual(code["version"], "1.6.33")
        self.assertEqual(code["commit_hash"], commit_hash)
        self.assertIsNone(code["core_dependency"])

    def test_other_software_version_text_is_preserved(self):
        """Leave other software version strings unchanged."""
        version = "branch:main commit ID:94823a7969e2f423cdb2eab12d55023efe4c5156 version:1.6.33"
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "training stimulus",
            "stimulus_modalities": ["Visual"],
            "script": None,
            "software": [{"name": "other-task", "version": version}],
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)
        code = upgraded_epoch["code"]

        self.assertEqual(code["version"], version)
        self.assertIsNone(code["commit_hash"])

    def test_script_remains_code_when_runtime_software_is_present(self):
        """Keep script metadata as Code and map runtime software as dependency."""
        epoch = {
            "stimulus_start_time": "2025-09-25T10:00:00-07:00",
            "stimulus_end_time": "2025-09-25T11:00:00-07:00",
            "stimulus_name": "opto tagging",
            "stimulus_modalities": ["Visual"],
            "script": {
                "name": "OptoTagging",
                "version": "a498cb9582051b2fba3ccdbd4703cd97ad4033ad",
                "url": "https://example.test/OptoTagging.py",
                "parameters": {},
            },
            "software": [{"name": "PsychoPy", "version": "2022.1.2"}],
        }

        upgraded_epoch = self.upgrader._upgrade_stimulus_epoch(epoch)
        code = upgraded_epoch["code"]

        self.assertEqual(code["name"], "OptoTagging")
        self.assertEqual(code["url"], "https://example.test/OptoTagging.py")
        self.assertEqual(code["core_dependency"]["name"], "PsychoPy")
        self.assertEqual(code["core_dependency"]["version"], "2022.1.2")


class TestUpgradeOphysFovToPlane(unittest.TestCase):
    """Tests for _upgrade_ophys_fov_to_plane"""

    def setUp(self):
        """Set up a SessionV1V2 upgrader instance for testing"""
        self.upgrader = SessionV1V2()

    def test_null_imaging_depth_defaults_to_zero(self):
        """imaging_depth present but explicitly null does not crash float()"""
        fov = {"imaging_depth": None, "targeted_structure": None}

        plane = self.upgrader._upgrade_ophys_fov_to_plane(fov)

        self.assertEqual(plane["depth"], 0.0)

    def test_missing_imaging_depth_defaults_to_zero(self):
        """imaging_depth absent entirely also defaults to zero"""
        fov = {"targeted_structure": None}

        plane = self.upgrader._upgrade_ophys_fov_to_plane(fov)

        self.assertEqual(plane["depth"], 0.0)

    def test_numeric_imaging_depth_is_preserved(self):
        """A real imaging_depth value passes through unchanged"""
        fov = {"imaging_depth": 150, "targeted_structure": None}

        plane = self.upgrader._upgrade_ophys_fov_to_plane(fov)

        self.assertEqual(plane["depth"], 150.0)


if __name__ == "__main__":
    unittest.main()
