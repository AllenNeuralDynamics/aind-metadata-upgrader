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
    """Unit tests for _extract_base_name."""

    def test_strips_camera_suffix(self):
        self.assertEqual(_extract_base_name("Face Camera"), "Face")
        self.assertEqual(_extract_base_name("Behavior Camera"), "Behavior")
        self.assertEqual(_extract_base_name("Eye camera"), "Eye")
        self.assertEqual(_extract_base_name("Eye CAMERA"), "Eye")

    def test_no_suffix(self):
        self.assertEqual(_extract_base_name("Eye"), "Eye")
        self.assertEqual(_extract_base_name("Behavior"), "Behavior")

    def test_strips_trailing_whitespace(self):
        self.assertEqual(_extract_base_name("Face Camera  "), "Face")

    def test_strips_camera_assembly_suffix(self):
        self.assertEqual(_extract_base_name("Face camera assembly"), "Face")
        self.assertEqual(_extract_base_name("Behavior Camera Assembly"), "Behavior")

    def test_does_not_strip_mid_string_camera(self):
        # 'Camera' in the middle (not at end) should be left alone
        self.assertEqual(_extract_base_name("Infrared Camera Side"), "Infrared Camera Side")


class TestGetSessionCameraNames(unittest.TestCase):
    """Unit tests for _get_session_camera_names."""

    def test_single_stream(self):
        session = _make_session([["Behavior", "Eye", "Face"]])
        self.assertEqual(
            _get_session_camera_names(session), ["Behavior", "Eye", "Face"]
        )

    def test_multiple_streams_deduplicates(self):
        session = _make_session([["Behavior", "Eye"], ["Eye", "Face"]])
        names = _get_session_camera_names(session)
        self.assertEqual(names, ["Behavior", "Eye", "Face"])

    def test_empty_session(self):
        self.assertEqual(_get_session_camera_names({}), [])

    def test_no_data_streams(self):
        self.assertEqual(_get_session_camera_names({"data_streams": []}), [])

    def test_streams_without_camera_names_key(self):
        session = {"data_streams": [{"other_key": "value"}]}
        self.assertEqual(_get_session_camera_names(session), [])

    def test_filters_empty_strings(self):
        session = _make_session([["Face", "", "Eye"]])
        names = _get_session_camera_names(session)
        self.assertNotIn("", names)
        self.assertIn("Face", names)
        self.assertIn("Eye", names)


class TestGetRigCameraAssemblyNames(unittest.TestCase):
    """Unit tests for _get_rig_camera_assembly_names."""

    def test_cameras_section(self):
        rig = _make_rig(["Behavior Camera", "Eye Camera", "Face Camera"])
        self.assertEqual(
            _get_rig_camera_assembly_names(rig),
            ["Behavior Camera", "Eye Camera", "Face Camera"],
        )

    def test_camera_assemblies_section(self):
        rig = _make_rig(["Behavior Camera"], section="camera_assemblies")
        self.assertEqual(_get_rig_camera_assembly_names(rig), ["Behavior Camera"])

    def test_both_sections_combined(self):
        rig = {
            "cameras": [{"name": "Behavior Camera", "camera": {}}],
            "camera_assemblies": [{"name": "Side Camera", "camera": {}}],
        }
        names = _get_rig_camera_assembly_names(rig)
        self.assertIn("Behavior Camera", names)
        self.assertIn("Side Camera", names)

    def test_deduplicates(self):
        rig = {
            "cameras": [{"name": "Behavior Camera"}, {"name": "Behavior Camera"}],
            "camera_assemblies": [],
        }
        names = _get_rig_camera_assembly_names(rig)
        self.assertEqual(names.count("Behavior Camera"), 1)

    def test_empty_rig(self):
        self.assertEqual(_get_rig_camera_assembly_names({}), [])


class TestBuildCameraNormalizationPlan(unittest.TestCase):
    """Unit tests for _build_camera_normalization_plan."""

    def test_standard_case(self):
        plan = _build_camera_normalization_plan(
            ["Behavior Camera", "Eye Camera", "Face Camera"]
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face Camera"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face Camera"]["camera_name"], "Face camera")
        self.assertEqual(plan["Behavior Camera"]["assembly_name"], "Behavior camera assembly")
        self.assertEqual(plan["Eye Camera"]["assembly_name"], "Eye camera assembly")

    def test_already_no_suffix(self):
        """Rig name with no ' Camera' suffix: base IS the full name."""
        plan = _build_camera_normalization_plan(["Face"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face"]["camera_name"], "Face camera")

    def test_ambiguous_bases_returns_none(self):
        """'Face Camera' and 'Face' both produce base 'Face' -> None."""
        plan = _build_camera_normalization_plan(["Face Camera", "Face"])
        self.assertIsNone(plan)

    def test_empty_returns_empty_dict(self):
        self.assertEqual(_build_camera_normalization_plan([]), {})

    def test_base_lower_field(self):
        plan = _build_camera_normalization_plan(["Face Camera"])
        self.assertEqual(plan["Face Camera"]["base_lower"], "face")

    def test_case_insensitive_suffix(self):
        plan = _build_camera_normalization_plan(["Face CAMERA"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan["Face CAMERA"]["assembly_name"], "Face camera assembly")
        self.assertEqual(plan["Face CAMERA"]["camera_name"], "Face camera")


class TestNormalizeCameraNames(unittest.TestCase):
    """Integration tests for normalize_camera_names."""

    def _build_data(self, session_cameras, rig_camera_names):
        return {
            "session": _make_session([session_cameras]),
            "rig": _make_rig(rig_camera_names),
        }

    def test_renames_rig_assembly_to_canonical_form(self):
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
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        inner_name = result["rig"]["cameras"][0]["camera"]["name"]
        self.assertEqual(inner_name, "Face camera")

    def test_assembly_name_differs_from_inner_camera_name(self):
        """Canonical names must be distinct to avoid duplicate-component warnings."""
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        assembly_name = result["rig"]["cameras"][0]["name"]
        inner_name = result["rig"]["cameras"][0]["camera"]["name"]
        self.assertNotEqual(assembly_name, inner_name)

    def test_session_camera_names_updated_to_assembly_name(self):
        """Session camera_names must be updated to the new assembly name."""
        data = self._build_data(["Face"], ["Face Camera"])
        result = normalize_camera_names(data)
        stream_names = result["session"]["data_streams"][0]["camera_names"]
        self.assertIn("Face camera assembly", stream_names)
        self.assertNotIn("Face", stream_names)

    def test_unmatched_session_camera_preserved(self):
        """Session cameras with no rig counterpart (e.g. Mesoscope) are left alone."""
        data = self._build_data(
            ["Behavior", "Mesoscope"],
            ["Behavior Camera"],
        )
        result = normalize_camera_names(data)
        stream_names = result["session"]["data_streams"][0]["camera_names"]
        self.assertIn("Mesoscope", stream_names)
        self.assertIn("Behavior camera assembly", stream_names)

    def test_already_canonical_returns_same_object(self):
        """If names are already canonical, return the original unchanged."""
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
        data = {"session": _make_session([["Face"]])}
        result = normalize_camera_names(data)
        self.assertIs(result, data)

    def test_ambiguous_rig_no_rename(self):
        """Two rig cameras with same base -> skip normalisation entirely."""
        data = self._build_data(["Face"], ["Face Camera", "Face"])
        result = normalize_camera_names(data)
        rig_names = [c["name"] for c in result["rig"]["cameras"]]
        self.assertIn("Face Camera", rig_names)
        self.assertIn("Face", rig_names)

    def test_original_not_mutated(self):
        data = self._build_data(["Face"], ["Face Camera"])
        original_rig_name = data["rig"]["cameras"][0]["name"]
        normalize_camera_names(data)
        self.assertEqual(data["rig"]["cameras"][0]["name"], original_rig_name)

    def test_camera_assemblies_section(self):
        data = {
            "session": _make_session([["Face"]]),
            "rig": _make_rig(["Face Camera"], section="camera_assemblies"),
        }
        result = normalize_camera_names(data)
        self.assertEqual(
            result["rig"]["camera_assemblies"][0]["name"], "Face camera assembly"
        )

    def test_case_insensitive_suffix(self):
        """'Face CAMERA' should produce the same canonical names."""
        data = self._build_data(["Face"], ["Face CAMERA"])
        result = normalize_camera_names(data)
        self.assertEqual(result["rig"]["cameras"][0]["name"], "Face camera assembly")
        self.assertEqual(result["rig"]["cameras"][0]["camera"]["name"], "Face camera")


class TestPreUpgradeNormalize(unittest.TestCase):
    """Smoke-test for the public pre_upgrade_normalize entry point."""

    def test_delegates_to_camera_normalization(self):
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
        data: dict = {}
        result = pre_upgrade_normalize(data)
        self.assertIs(result, data)


if __name__ == "__main__":
    unittest.main()
