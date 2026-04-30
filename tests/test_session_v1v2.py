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


if __name__ == "__main__":
    unittest.main()
