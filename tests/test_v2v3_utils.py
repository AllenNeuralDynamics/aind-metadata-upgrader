"""Tests for shared v2 to v3 upgrade helpers."""

import unittest

from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade


class TestV2V3Utils(unittest.TestCase):
    """Test shared v2 to v3 rewrites."""

    @staticmethod
    def _axis(name, direction):
        return {"object_type": "Axis", "name": name, "direction": direction}

    @staticmethod
    def _coordinate_system(axes):
        return {
            "object_type": "Coordinate system",
            "name": "TEST",
            "origin": "Origin",
            "axis_unit": "millimeter",
            "axes": axes,
        }

    def test_missing_code_versions_are_repaired_recursively(self):
        """Missing and null Code versions receive the standard placeholder."""
        data = {
            "object_type": "Acquisition",
            "code": {"object_type": "Code", "url": "https://example.com/missing"},
            "nested": [{"object_type": "Code", "url": "https://example.com/null", "version": None}],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(upgraded["code"]["version"], "unknown")
        self.assertEqual(upgraded["nested"][0]["version"], "unknown")

    def test_existing_code_version_is_preserved(self):
        """An explicitly supplied Code version is not overwritten."""
        data = {"object_type": "Code", "url": "https://example.com/code", "version": "1.2.3"}

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(upgraded["version"], "1.2.3")

    def test_depth_becomes_local_device_translation(self):
        """Device depth is represented by a local translation after axis removal."""
        data = {
            "object_type": "Probe config",
            "coordinate_system": self._coordinate_system(
                [
                    self._axis("X", "Left_to_right"),
                    self._axis("Y", "Back_to_front"),
                    self._axis("Z", "Up_to_down"),
                    self._axis("Depth", "Up_to_down"),
                ]
            ),
            "transform": [{"object_type": "Translation", "translation": [1, 2, 3, 4]}],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual([axis["name"] for axis in upgraded["local_coordinate_system"]["axes"]], ["X", "Y", "Z"])
        self.assertEqual(upgraded["transform"][0]["translation"], [1, 2, 3])
        self.assertEqual(upgraded["transform"][1]["translation"], [0, 0, 4])
        self.assertEqual(upgraded["transform"][1]["reference_coordinate_system"], "local")

    def test_opposite_device_axis_reverses_depth(self):
        """Depth is negated when the remaining device axis points upward."""
        data = {
            "object_type": "Probe config",
            "coordinate_system": self._coordinate_system(
                [
                    self._axis("X", "Left_to_right"),
                    self._axis("Y", "Down_to_up"),
                    self._axis("Z", "Back_to_front"),
                    self._axis("Depth", "Up_to_down"),
                ]
            ),
            "transform": [{"object_type": "Translation", "translation": [1, 2, 3, 4]}],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(upgraded["transform"][1]["translation"], [0, -4, 0])

    def test_global_injection_depth_uses_remaining_vertical_axis(self):
        """Global injection depth is folded into the global vertical coordinate."""
        data = {
            "object_type": "Procedures",
            "global_coordinate_system": self._coordinate_system(
                [
                    self._axis("AP", "Posterior_to_anterior"),
                    self._axis("ML", "Left_to_right"),
                    self._axis("SI", "Superior_to_inferior"),
                    self._axis("Depth", "Up_to_down"),
                ]
            ),
            "subject_procedures": [
                {
                    "object_type": "Brain injection",
                    "coordinates": [[{"object_type": "Translation", "translation": [1, 2, 0, 3]}]],
                }
            ],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(upgraded["global_coordinate_system"]["axes"][-1]["name"], "SI")
        self.assertEqual(
            upgraded["subject_procedures"][0]["coordinates"][0][0]["translation"],
            [1, 2, 3],
        )

    def test_three_component_transforms_are_unchanged(self):
        """Transforms that already match the post-migration axes are preserved."""
        data = {
            "object_type": "Probe config",
            "coordinate_system": self._coordinate_system(
                [
                    self._axis("X", "Left_to_right"),
                    self._axis("Y", "Back_to_front"),
                    self._axis("Z", "Up_to_down"),
                    self._axis("Depth", "Up_to_down"),
                ]
            ),
            "transform": [{"object_type": "Translation", "translation": [1, 2, 3]}],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(upgraded["transform"], [{"object_type": "Translation", "translation": [1, 2, 3]}])

    def test_four_dimensional_affine_transform_loses_depth_row_and_column(self):
        """Affine matrices are reduced to the post-migration coordinate dimension."""
        data = {
            "object_type": "Probe config",
            "coordinate_system": self._coordinate_system(
                [
                    self._axis("X", "Left_to_right"),
                    self._axis("Y", "Back_to_front"),
                    self._axis("Z", "Up_to_down"),
                    self._axis("Depth", "Up_to_down"),
                ]
            ),
            "transform": [
                {
                    "object_type": "Affine",
                    "affine_transform": [
                        [1, 0, 0, 0, 1],
                        [0, 1, 0, 0, 2],
                        [0, 0, 1, 0, 3],
                        [0, 0, 0, 1, 4],
                        [0, 0, 0, 0, 1],
                    ],
                }
            ],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(
            upgraded["transform"][0]["affine_transform"],
            [[1, 0, 0, 1], [0, 1, 0, 2], [0, 0, 1, 3], [0, 0, 0, 1]],
        )

    def test_three_dimensional_affine_transform_gets_homogeneous_row_and_column(self):
        """Three-dimensional legacy affine matrices receive the v3 homogeneous border."""
        data = {
            "object_type": "Instrument",
            "coordinate_system": self._coordinate_system(
                [
                    self._axis("X", "Left_to_right"),
                    self._axis("Y", "Back_to_front"),
                    self._axis("Z", "Up_to_down"),
                ]
            ),
            "components": [
                {
                    "object_type": "Detector",
                    "transform": [
                        {
                            "object_type": "Affine",
                            "affine_transform": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                        }
                    ],
                }
            ],
        }

        upgraded = recursive_upgrade(data, {})

        self.assertEqual(
            upgraded["components"][0]["transform"][0]["affine_transform"],
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        )
