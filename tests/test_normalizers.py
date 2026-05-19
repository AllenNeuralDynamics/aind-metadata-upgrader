"""Tests for pre-upgrade normalisation utilities."""

import unittest

from aind_metadata_upgrader.utils.normalizers import (
    _build_camera_normalization_plan,
    _extract_base_name,
    _get_rig_camera_assembly_names,
    _get_session_camera_names,
    normalize_camera_names,
    pre_upgrade_normalize,
)


def _make_session(camera_name_groups):
    """Build a minimal v1 session dict with the given camera name groups."""
    return {
        "data_streams": [
            {"camera_names": names} for names in camera_name_groups
        ]
    }


def _make_rig(camera_names, section="cameras"):
    """Build a minimal v1 rig dict with the given camera assembly names."""
    return {
        section: [
            {
                "name": name,
                "camera": {"name": name},
                "camera_target": "Face",
            }
            for name in camera_names
        ]
    }


class TestExtractBaseName(unittest.TestCase):
    """Test _extract_base_name."""

    def test_strips_camera_suffix(self):
        """Strip camera suffix."""
        self.assertEqual(_extract_base_name("Face Camera"), "Face")
        self.assertEqual(_extract_base_name("Behavior Camera"), "Behavior")
        self.assertEqual(_extract_base_name("Eye camera"), "Eye")
        self.assertEqual(_extract_base_name("Eye CAMERA"), "Eye")

    def test_no_suffix(self):
        """No suffix returns unchanged."""
        self.assertEqual(_extract_base_name("Eye"), "Eye")
        self.assertEqual(_extract_base_name("Behavior"), "Behavior")

    def test_strips_trailing_whitespace(self):
        """Strip trailing whitespace."""
        self.assertEqual(_extract_base_name("Face Camera  "), "Face")

    def test_strips_camera_assembly_suffix(self):
        """Strip assembly suffix."""
        self.assertEqual(_extract_base_name("Face camera assembly"), "Face")
        self.assertEqual(_extract_base_name("Behavior Camera Assembly"), "Behavior")

    def test_does_not_strip_mid_string_camera(self):
        """Preserve mid-string 'Camera'."""
        # 'Camera' in the middle (not at end) should be left alone
        self.assertEqual(_extract_base_name("Infrared Camera Side"), "Infrared Camera Side")


class TestGetSessionCameraNames(unittest.TestCase):
    """Test _get_session_camera_names."""

    def test_single_stream(self):
        """Single stream."""
        session = _make_session([["Behavior", "Eye", "Face"]])
        self.assertEqual(
            _get_session_camera_names(session), ["Behavior", "Eye", "Face"]
        )

    def test_multiple_streams_deduplicates(self):
        """Deduplicate across streams."""
        session = _make_session([["Behavior", "Eye"], ["Eye", "Face"]])
        names = _get_session_camera_names(session)
        self.assertEqual(names, ["Behavior", "Eye", "Face"])

    def test_empty_session(self):
        """Empty session."""
        self.assertEqual(_get_session_camera_names({}), [])

    def test_no_data_streams(self):
        """No data streams."""
        self.assertEqual(_get_session_camera_names({"data_streams": []}), [])

    def test_streams_without_camera_names_key(self):
        """Missing camera_names key."""
        session = {"data_streams": [{"other_key": "value"}]}
        self.assertEqual(_get_session_camera_names(session), [])

    def test_filters_empty_strings(self):
        """Filter empty strings."""
        session = _make_session([["Face", "", "Eye"]])
        names = _get_session_camera_names(session)
        self.assertNotIn("", names)
        self.assertIn("Face", names)
        self.assertIn("Eye", names)


class TestGetRigCameraAssemblyNames(unittest.TestCase):
    """Test _get_rig_camera_assembly_names."""

    def test_cameras_section(self):
        """Cameras section."""
        rig = _make_rig(["Behavior Camera", "Eye Camera", "Face Camera"])
        self.assertEqual(
            _get_rig_camera_assembly_names(rig),
            ["Behavior Camera", "Eye Camera", "Face Camera"],
        )

    def test_camera_assemblies_section(self):
        """Camera assemblies section."""
        rig = _make_rig(["Behavior Camera"], section="camera_assemblies")
        self.assertEqual(_get_rig_camera_assembly_names(rig), ["Behavior Camera"])

    def test_both_sections_combined(self):
        """Both sections combined."""
        rig = {
            "cameras": [{"name": "Behavior Camera", "camera": {}}],
            "camera_assemblies": [{"name": "Side Camera", "camera": {}}],
        }
        names = _get_rig_camera_assembly_names(rig)
        self.assertIn("Behavior Camera", names)
        self.assertIn("Side Camera", names)

    def test_deduplicates(self):
        """Deduplicate entries."""
        rig = {
            "cameras": [{"name": "Behavior Camera"}, {"name": "Behavior Camera"}],
            "camera_assemblies": [],
        }
        names = _get_rig_camera_assembly_names(rig)
        self.assertEqual(names.count("Behavior Camera"), 1)

    def test_empty_rig(self):
        """Empty rig."""
        self.assertEqual(_get_rig_camera_assembly_names({}), [])


class TestBuildCameraNormalizationPlan(unittest.TestCase):
    """Test _build_camera_normalization_plan."""

    def test_standard_case(self):
        """Standard normalization."""
        plan = _build_camera_normalization_plan(
            ["Behavior Camera", "Eye Camera", "Face Camera"]
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face Camera"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face Camera"]["camera_name"], "Face camera")
        self.assertEqual(plan["Behavior Camera"]["assembly_name"], "Behavior camera assembly")
        self.assertEqual(plan["Eye Camera"]["assembly_name"], "Eye camera assembly")

    def test_already_no_suffix(self):
        """No suffix: base is full name."""
        plan = _build_camera_normalization_plan(["Face"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face"]["camera_name"], "Face camera")

    def test_ambiguous_bases_returns_none(self):
        """Ambiguous bases return None."""
        plan = _build_camera_normalization_plan(["Face Camera", "Face"])
        self.assertIsNone(plan)

    def test_empty_returns_empty_dict(self):
        """Empty input returns empty dict."""
        self.assertEqual(_build_camera_normalization_plan([]), {})

    def test_base_lower_field(self):
        """Base lower field."""
        plan = _build_camera_normalization_plan(["Face Camera"])
        self.assertEqual(plan["Face Camera"]["base_lower"], "face")

    def test_case_insensitive_suffix(self):
        """Case-insensitive suffix."""
        plan = _build_camera_normalization_plan(["Face CAMERA"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face CAMERA"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face CAMERA"]["camera_name"], "Face camera")


class TestNormalizeCameraNames(unittest.TestCase):
    """Test normalize_camera_names."""

    def _build_data(self, session_cameras, rig_camera_names):
        """Build a minimal input dict with the given session and rig camera names."""
        return {
            "session": _make_session([session_cameras]),
            "rig": _make_rig(rig_camera_names),
        }

    def test_renames_rig_assembly_to_canonical_form(self):
        """Rename rig assembly to canonical form."""
        data = self._build_data(
            ["Behavior", "Eye", "Face"],
            ["Behavior Camera", "Eye Camera", "Face Camera"],
        )
        result = normalize_camera_names(data)
        rig_names = sorted(c["name"] for c in result["rig"]["cameras"])
        self.assertEqual(rig_names, [
            "Behavior camera assembly",
            "Eye camera assembly",
            "Face camera assembly",
        ])

    def test_renames_inner_camera_to_canonical_form(self):
        """Rename inner camera to canonical form."""
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        inner_name = result["rig"]["cameras"][0]["camera"]["name"]
        self.assertEqual(inner_name, "Face camera")

    def test_assembly_name_differs_from_inner_camera_name(self):
        """Assembly and camera names distinct."""
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        assembly_name = result["rig"]["cameras"][0]["name"]
        inner_name = result["rig"]["cameras"][0]["camera"]["name"]
        self.assertNotEqual(assembly_name, inner_name)

    def test_session_camera_names_updated_to_assembly_name(self):
        """Session camera names updated to assembly name."""
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        stream_names = result["session"]["data_streams"][0]["camera_names"]
        self.assertIn("Face camera assembly", stream_names)
        self.assertNotIn("Face", stream_names)

    def test_unmatched_session_camera_preserved(self):
        """Unmatched session cameras preserved."""
        data = self._build_data(
            ["Behavior", "Mesoscope"],
            ["Behavior Camera"],
        )
        result = normalize_camera_names(data)
        stream_names = result["session"]["data_streams"][0]["camera_names"]
        self.assertIn("Mesoscope", stream_names)
        self.assertIn("Behavior camera assembly", stream_names)

    def test_already_canonical_returns_same_object(self):
        """Already canonical returns unchanged."""
        data = {
            "session": _make_session([["Face camera assembly"]]),
            "rig": {
                "cameras": [{
                    "name": "Face camera assembly",
                    "camera": {"name": "Face camera"},
                    "camera_target": "Face",
                }]
            },
        }
        result = normalize_camera_names(data)
        self.assertIs(result, data)

    def test_no_rig_returns_original(self):
        """No rig returns original."""
        data = {"session": _make_session([["Face"]])}
        result = normalize_camera_names(data)
        self.assertIs(result, data)

    def test_ambiguous_rig_no_rename(self):
        """Ambiguous rig skips normalization."""
        data = self._build_data(["Face"], ["Face Camera", "Face"])
        result = normalize_camera_names(data)
        rig_names = [c["name"] for c in result["rig"]["cameras"]]
        self.assertIn("Face Camera", rig_names)
        self.assertIn("Face", rig_names)

    def test_original_not_mutated(self):
        """Original data not mutated."""
        data = self._build_data(["Face"], ["Face Camera"])
        original_rig_name = data["rig"]["cameras"][0]["name"]
        normalize_camera_names(data)
        self.assertEqual(data["rig"]["cameras"][0]["name"], original_rig_name)

    def test_camera_assemblies_section(self):
        """Camera assemblies section."""
        data = {
            "session": _make_session([["Face"]]),
            "rig": _make_rig(["Face Camera"], section="camera_assemblies"),
        }
        result = normalize_camera_names(data)
        self.assertEqual(
            result["rig"]["camera_assemblies"][0]["name"], "Face camera assembly"
        )

    def test_case_insensitive_suffix(self):
        """Case-insensitive suffix same canonical names."""
        data = self._build_data(["Face"], ["Face CAMERA"])
        result = normalize_camera_names(data)
        self.assertEqual(result["rig"]["cameras"][0]["name"], "Face camera assembly")
        self.assertEqual(result["rig"]["cameras"][0]["camera"]["name"], "Face camera")


class TestPreUpgradeNormalize(unittest.TestCase):
    """Test pre_upgrade_normalize."""

    def test_delegates_to_camera_normalization(self):
        """Delegates to camera normalization."""
        data = {
            "session": _make_session([["Behavior", "Eye", "Face"]]),
            "rig": _make_rig(["Behavior Camera", "Eye Camera", "Face Camera"]),
        }
        result = pre_upgrade_normalize(data)
        rig_names = sorted(c["name"] for c in result["rig"]["cameras"])
        self.assertEqual(rig_names, [
            "Behavior camera assembly",
            "Eye camera assembly",
            "Face camera assembly",
        ])
        stream_names = result["session"]["data_streams"][0]["camera_names"]
        self.assertIn("Face camera assembly", stream_names)

    def test_no_op_for_empty_record(self):
        """Empty record is no-op."""
        data: dict = {}
        result = pre_upgrade_normalize(data)
        self.assertIs(result, data)


if __name__ == "__main__":
    unittest.main()
