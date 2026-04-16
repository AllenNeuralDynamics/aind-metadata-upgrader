"""Tests for acquisition v1v2 upgrade functionality"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from aind_data_schema.core.acquisition import Acquisition

from aind_metadata_upgrader.acquisition.v1v2 import AcquisitionV1V2
from aind_metadata_upgrader.acquisition.v1v2_tiles import (
    _create_detector_config,
    _create_laser_config_from_channel,
    convert_tiles_to_images,
    extract_channels_from_tiles,
)

RECORDS_DIR = Path(__file__).parent / "records"


# ── Helpers to build V1 test data inline ────────────────────────────────

EXASPIM_AXES = [
    {"name": "X", "direction": "Inferior_to_superior", "dimension": 2, "unit": "micrometer"},
    {"name": "Y", "direction": "Anterior_to_posterior", "dimension": 1, "unit": "micrometer"},
    {"name": "Z", "direction": "Left_to_right", "dimension": 0, "unit": "micrometer"},
]


def _make_tile(file_name, channel_name, light_source_name, detector_name,
               excitation_wavelength, excitation_power,
               scale=("15.04", "15.04", "20.0"),
               translation=("-59.1512", "12.3668", "-38.3913"),
               additional_device_names=None):
    """Build a minimal V1 tile dict."""
    return {
        "coordinate_transformations": [
            {"type": "scale", "scale": list(scale)},
            {"type": "translation", "translation": list(translation)},
        ],
        "file_name": file_name,
        "channel": {
            "channel_name": channel_name,
            "light_source_name": light_source_name,
            "filter_names": [],
            "detector_name": detector_name,
            "additional_device_names": additional_device_names or [],
            "excitation_wavelength": excitation_wavelength,
            "excitation_wavelength_unit": "nanometer",
            "excitation_power": excitation_power,
            "excitation_power_unit": "milliwatt",
            "filter_wheel_index": 0,
        },
        "notes": None,
        "imaging_angle": 0,
        "imaging_angle_unit": "degrees",
        "acquisition_start_time": None,
        "acquisition_end_time": None,
    }


def _make_v1_acquisition(tiles, axes=None, subject_id="765830", specimen_id="765830",
                          session_start="2025-11-21T12:01:47.108976-08:00",
                          session_end="2025-11-21T12:19:53.806266-08:00",
                          chamber_immersion=None):
    """Build a minimal V1 acquisition dict."""
    return {
        "schema_version": "1.0.4",
        "protocol_id": [],
        "experimenter_full_name": ["adam glaser"],
        "specimen_id": specimen_id,
        "subject_id": subject_id,
        "instrument_id": "",
        "calibrations": [],
        "maintenance": [],
        "session_start_time": session_start,
        "session_end_time": session_end,
        "session_type": None,
        "tiles": tiles,
        "axes": axes if axes is not None else EXASPIM_AXES,
        "chamber_immersion": chamber_immersion or {"medium": "other", "refractive_index": "1.33"},
        "sample_immersion": None,
        "active_objectives": None,
        "software": [],
        "notes": None,
    }


# Fixtures: pre-built V1 acquisition dicts ──────────────────────────────

# Single-channel exaSPIM: 2 tiles, both ch 488
SINGLE_CHANNEL_TILES = [
    _make_tile("tile_000000_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"]),
    _make_tile("tile_000001_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"]),
]
V1_SINGLE_CHANNEL = _make_v1_acquisition(SINGLE_CHANNEL_TILES)

# Multi-channel exaSPIM: 4 tiles, 2×561 + 2×488
MULTI_CHANNEL_TILES = [
    _make_tile("tile_000000_ch_561.ims", "561", "561 nm", "vnp-604mx", 561, 220.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               translation=("-41.5744", "13.1057", "-23.799")),
    _make_tile("tile_000000_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               scale=("30.08", "30.08", "40.0"),
               translation=("-41.5744", "13.1057", "-23.799")),
    _make_tile("tile_000001_ch_561.ims", "561", "561 nm", "vnp-604mx", 561, 220.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               translation=("-41.5744", "13.1057", "-23.799")),
    _make_tile("tile_000001_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               scale=("30.08", "30.08", "40.0"),
               translation=("-41.5744", "13.1057", "-23.799")),
]
V1_MULTI_CHANNEL = _make_v1_acquisition(
    MULTI_CHANNEL_TILES,
    subject_id="822178-1x", specimen_id="822178-1x",
    session_start="2026-04-03T15:46:33.698599-07:00",
    session_end="2026-04-03T16:19:57.552352-07:00",
)

# Duplicate-channel tiles (single channel, 2 tiles — tests deduplication)
DEDUP_TILES = [
    _make_tile("right_000000_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               translation=("-43.6593", "10.7756", "-26.8994")),
    _make_tile("left_000001_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
               additional_device_names=["camera", "left_right_flip_mount"],
               translation=("-43.6593", "10.7756", "-26.8994")),
]
V1_DEDUP = _make_v1_acquisition(
    DEDUP_TILES,
    subject_id="669977", specimen_id="669977",
    session_start="2026-03-02T16:48:27.843696-08:00",
    session_end="2026-03-02T17:02:52.931553-08:00",
)


class TestAcquisitionV1V2(unittest.TestCase):
    """Test the AcquisitionV1V2 class"""

    def setUp(self):
        """Setup"""
        self.upgrader = AcquisitionV1V2()

    def test_upgrade_with_invalid_data_type(self):
        """Test upgrade method with non-dict data"""
        with self.assertRaises(ValueError) as context:
            self.upgrader.upgrade("not a dict", "2.0.34", metadata={})  # type: ignore
        self.assertEqual(str(context.exception), "Data must be a dictionary")

    def test_determine_acquisition_type_with_session_type(self):
        """Test _determine_acquisition_type when session_type exists"""
        data = {"session_type": "Custom Session Type"}
        result = self.upgrader._determine_acquisition_type(data)
        self.assertEqual(result, "Custom Session Type")

    def test_determine_acquisition_type_with_tiles_no_session_type(self):
        """Test _determine_acquisition_type when tiles exist but no session_type"""
        data = {"tiles": [{"some": "tile"}]}
        result = self.upgrader._determine_acquisition_type(data)
        self.assertEqual(result, "Imaging session")

    def test_upgrade_with_string_datetime(self):
        """Test upgrade with string datetime"""
        with patch("aind_metadata_upgrader.acquisition.v1v2.upgrade_tiles_to_data_stream") as mock_upgrade_tiles:
            mock_upgrade_tiles.return_value = [{"active_devices": []}]
            with patch("aind_metadata_upgrader.acquisition.v1v2.upgrade_calibration") as mock_upgrade_cal:
                mock_upgrade_cal.return_value = {}
                data = {
                    "subject_id": "test_subject",
                    "session_start_time": "2024-01-01T10:00:00",
                    "session_end_time": "2024-01-01T11:00:00",
                    "calibrations": [],
                    "maintenance": [],
                }
                result = self.upgrader.upgrade(data, "2.0.34", metadata={"instrument": {}})
                self.assertIsNotNone(result)
                self.assertEqual(result["subject_id"], "test_subject")

    def test_upgrade_without_session_times(self):
        """Test upgrade without session times raises NotImplementedError"""
        data = {"subject_id": "test_subject"}
        with self.assertRaises(NotImplementedError):
            self.upgrader.upgrade(data, "2.0.34", metadata={})


# ── Unit tests for detector config ──────────────────────────────────────


class TestDetectorConfig(unittest.TestCase):
    """Test _create_detector_config uses tile channel data"""

    def test_uses_tile_detector_name(self):
        """Detector config should use the detector_name from tile channel data"""
        channel_data = {"detector_name": "vnp-604mx"}
        result = _create_detector_config(channel_data)
        self.assertEqual(result.device_name, "vnp-604mx")

    def test_falls_back_to_unknown(self):
        """Detector config falls back to 'unknown_detector' when no name present"""
        result = _create_detector_config({})
        self.assertEqual(result.device_name, "unknown_detector")

    def test_uses_pmt_name(self):
        """Detector config correctly handles PMT-style detector names"""
        channel_data = {"detector_name": "PMT_1"}
        result = _create_detector_config(channel_data)
        self.assertEqual(result.device_name, "PMT_1")


# ── Unit tests for laser config ─────────────────────────────────────────


class TestLaserConfigFromChannel(unittest.TestCase):
    """Test _create_laser_config_from_channel handles V1 tile keys"""

    def test_excitation_wavelength_creates_laser_config(self):
        """Tile data with excitation_wavelength should produce a LaserConfig"""
        channel_data = {
            "excitation_wavelength": 488,
            "excitation_power": 197.0,
            "excitation_power_unit": "milliwatt",
            "light_source_name": "488 nm",
        }
        result = _create_laser_config_from_channel(channel_data)
        self.assertEqual(len(result), 1)
        laser = result[0]
        self.assertEqual(laser.device_name, "488 nm")
        self.assertEqual(laser.wavelength, 488)
        self.assertEqual(laser.power, 197.0)

    def test_excitation_wavelength_without_power(self):
        """Tile data with excitation_wavelength but no power still creates LaserConfig"""
        channel_data = {
            "excitation_wavelength": 561,
            "light_source_name": "561 nm",
        }
        result = _create_laser_config_from_channel(channel_data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].wavelength, 561)
        self.assertIsNone(result[0].power)

    def test_legacy_laser_wavelength_still_works(self):
        """Legacy laser_wavelength key should still work"""
        channel_data = {
            "laser_wavelength": 488,
            "laser_power": 100.0,
            "laser_power_unit": "milliwatt",
        }
        result = _create_laser_config_from_channel(channel_data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].wavelength, 488)

    def test_no_wavelength_returns_empty(self):
        """Channel data without any wavelength key returns empty list"""
        result = _create_laser_config_from_channel({"channel_name": "488"})
        self.assertEqual(result, [])

    def test_fallback_device_name_from_wavelength(self):
        """When light_source_name is absent, device_name uses wavelength"""
        channel_data = {"excitation_wavelength": 405}
        result = _create_laser_config_from_channel(channel_data)
        self.assertEqual(result[0].device_name, "laser_405nm")


# ── Unit tests for coordinate system ────────────────────────────────────


class TestCoordinateSystem(unittest.TestCase):
    """Test coordinate system axis name preservation"""

    def setUp(self):
        self.upgrader = AcquisitionV1V2()

    def test_preserves_original_axis_names(self):
        """Axes should keep their original V1 names (X/Y/Z) with correct directions"""
        result = self.upgrader._create_coordinate_system_from_axes(EXASPIM_AXES)

        self.assertEqual(result["name"], "SPIM_RPS")
        # Axes are sorted by dimension: Z(dim0), Y(dim1), X(dim2)
        self.assertEqual(result["axes"][0]["name"], "Z")
        self.assertEqual(result["axes"][0]["direction"], "Left_to_right")
        self.assertEqual(result["axes"][1]["name"], "Y")
        self.assertEqual(result["axes"][1]["direction"], "Anterior_to_posterior")
        self.assertEqual(result["axes"][2]["name"], "X")
        self.assertEqual(result["axes"][2]["direction"], "Inferior_to_superior")

    def test_standard_xyz_ordering(self):
        """When dimension order matches axis names, axes are correct"""
        axes = [
            {"name": "X", "direction": "Left_to_right", "dimension": 0, "unit": "micrometer"},
            {"name": "Y", "direction": "Anterior_to_posterior", "dimension": 1, "unit": "micrometer"},
            {"name": "Z", "direction": "Superior_to_inferior", "dimension": 2, "unit": "micrometer"},
        ]
        result = self.upgrader._create_coordinate_system_from_axes(axes)
        self.assertEqual(result["axes"][0]["name"], "X")
        self.assertEqual(result["axes"][1]["name"], "Y")
        self.assertEqual(result["axes"][2]["name"], "Z")

    def test_returns_none_for_empty_axes(self):
        """Empty axes list returns None"""
        self.assertIsNone(self.upgrader._create_coordinate_system_from_axes([]))


# ── Unit tests for tile → ImageSPIM conversion ─────────────────────────


class TestConvertTilesToImages(unittest.TestCase):
    """Test convert_tiles_to_images creates ImageSPIM objects from V1 tiles"""

    def test_single_tile_produces_image(self):
        """A single V1 tile should produce one ImageSPIM"""
        tile = _make_tile("tile_000000_ch_488.ims", "488", "488 nm", "vnp-604mx", 488, 197.0,
                          translation=("-59.15", "12.37", "-38.39"))
        images = convert_tiles_to_images([tile])
        self.assertEqual(len(images), 1)
        img = images[0]
        self.assertEqual(img["object_type"], "Image spim")
        self.assertEqual(img["file_name"], "tile_000000_ch_488.ims")
        self.assertEqual(img["channel_name"], "488")
        self.assertEqual(img["imaging_angle"], 0)
        # Check transforms
        self.assertEqual(img["image_to_acquisition_transform"][0]["scale"], [15.04, 15.04, 20.0])
        self.assertAlmostEqual(img["image_to_acquisition_transform"][1]["translation"][0], -59.15)

    def test_multiple_tiles(self):
        """Multiple tiles each produce their own ImageSPIM"""
        tiles = [
            _make_tile(f"tile_{i:06d}_ch_488.ims", "488", "488 nm", "det", 488, 100.0,
                       scale=("1", "1", "1"), translation=("0", "0", "0"))
            for i in range(3)
        ]
        images = convert_tiles_to_images(tiles)
        self.assertEqual(len(images), 3)
        file_names = [img["file_name"] for img in images]
        self.assertEqual(file_names, [
            "tile_000000_ch_488.ims",
            "tile_000001_ch_488.ims",
            "tile_000002_ch_488.ims",
        ])


# ── Tests for instrument metadata being optional ────────────────────────


class TestInstrumentOptional(unittest.TestCase):
    """Test that upgrade works without instrument metadata"""

    def setUp(self):
        self.upgrader = AcquisitionV1V2()

    def test_upgrade_without_instrument_metadata(self):
        """Upgrade should succeed with empty metadata (no instrument)"""
        result = self.upgrader.upgrade(V1_SINGLE_CHANNEL, "2.6.0", metadata={})
        channels = result["data_streams"][0]["configurations"][0]["channels"]
        self.assertTrue(len(channels) > 0)
        self.assertNotEqual(channels[0]["detector"]["device_name"], "unknown_detector")

    def test_upgrade_with_none_metadata(self):
        """Upgrade should succeed when metadata is None"""
        result = self.upgrader.upgrade(V1_SINGLE_CHANNEL, "2.6.0", metadata=None)
        channels = result["data_streams"][0]["configurations"][0]["channels"]
        self.assertTrue(len(channels) > 0)

    def test_upgrade_with_instrument_light_sources(self):
        """When instrument has light_sources, channels still build correctly"""
        instrument_metadata = {
            "instrument": {
                "fluorescence_filters": [],
                "light_sources": [{"name": "488 nm", "wavelength": 488}],
            }
        }
        result = self.upgrader.upgrade(V1_SINGLE_CHANNEL, "2.6.0", metadata=instrument_metadata)
        channels = result["data_streams"][0]["configurations"][0]["channels"]
        self.assertTrue(len(channels[0]["light_sources"]) > 0)
        self.assertEqual(channels[0]["light_sources"][0]["device_name"], "488 nm")


# ── Integration (end-to-end) tests ──────────────────────────────────────


class TestEndToEndExaSPIM(unittest.TestCase):
    """Integration tests: full V1 → V2 upgrade with Pydantic validation"""

    def setUp(self):
        self.upgrader = AcquisitionV1V2()

    def _upgrade_and_validate(self, v1_data: dict) -> dict:
        """Run upgrade and validate against Pydantic model, return output dict"""
        result = self.upgrader.upgrade(v1_data, "2.6.0", metadata={})
        acq = Acquisition(**result)
        return acq.model_dump()

    def test_exaspim_single_channel_upgrade(self):
        """End-to-end: exaSPIM V1 single-channel (2 identical tiles)"""
        output = self._upgrade_and_validate(V1_SINGLE_CHANNEL)

        self.assertEqual(output["subject_id"], "765830")
        self.assertEqual(output["acquisition_type"], "Imaging session")
        self.assertEqual(len(output["data_streams"]), 1)

        stream = output["data_streams"][0]
        self.assertEqual(stream["modalities"][0]["abbreviation"], "SPIM")

        # Channels
        channels = stream["configurations"][0]["channels"]
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]["channel_name"], "488")
        self.assertEqual(channels[0]["detector"]["device_name"], "vnp-604mx")
        self.assertEqual(len(channels[0]["light_sources"]), 1)
        self.assertEqual(channels[0]["light_sources"][0]["device_name"], "488 nm")
        self.assertEqual(channels[0]["light_sources"][0]["wavelength"], 488)
        self.assertEqual(channels[0]["light_sources"][0]["power"], 197.0)

        # Coordinate system
        coord = output["coordinate_system"]
        self.assertEqual(coord["name"], "SPIM_RPS")
        axis_names = [a["name"] for a in coord["axes"]]
        self.assertEqual(axis_names, ["Z", "Y", "X"])

        # Images (tiles preserved)
        images = stream["configurations"][0]["images"]
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]["file_name"], "tile_000000_ch_488.ims")
        self.assertEqual(images[1]["file_name"], "tile_000001_ch_488.ims")
        self.assertEqual(images[0]["image_to_acquisition_transform"][0]["scale"], [15.04, 15.04, 20.0])

        # Active devices
        self.assertIn("vnp-604mx", stream["active_devices"])
        self.assertIn("488 nm", stream["active_devices"])
        self.assertIn("camera", stream["active_devices"])

    def test_exaspim_2tile_multichannel_upgrade(self):
        """End-to-end: exaSPIM V1 with 2 channels (488, 561), 4 tiles total"""
        output = self._upgrade_and_validate(V1_MULTI_CHANNEL)

        channels = output["data_streams"][0]["configurations"][0]["channels"]
        channel_names = sorted([ch["channel_name"] for ch in channels])
        self.assertEqual(channel_names, ["488", "561"])

        # Both channels use the same detector
        for ch in channels:
            self.assertEqual(ch["detector"]["device_name"], "vnp-604mx")
            self.assertTrue(len(ch["light_sources"]) > 0)

        # Correct wavelengths
        wavelengths = sorted([ch["light_sources"][0]["wavelength"] for ch in channels])
        self.assertEqual(wavelengths, [488, 561])

        # All 4 tiles preserved as images
        images = output["data_streams"][0]["configurations"][0]["images"]
        self.assertEqual(len(images), 4)

    def test_test_record_upgrade(self):
        """End-to-end: test record with PMT detector and named light sources"""
        with open(RECORDS_DIR / "acquisition" / "v1.json") as f:
            record = json.load(f)
        v1_data = record["acquisition"]

        output = self._upgrade_and_validate(v1_data)

        channels = output["data_streams"][0]["configurations"][0]["channels"]
        channel_names = sorted([ch["channel_name"] for ch in channels])
        self.assertEqual(channel_names, ["488", "561"])

        for ch in channels:
            self.assertEqual(ch["detector"]["device_name"], "PMT_1")

        light_source_names = sorted([ch["light_sources"][0]["device_name"] for ch in channels])
        self.assertEqual(light_source_names, ["Ex_488", "Ex_561"])

        # Tiles preserved as images
        images = output["data_streams"][0]["configurations"][0]["images"]
        self.assertEqual(len(images), 2)

    def test_single_tile_deduplication(self):
        """End-to-end: tiles with same channel are deduplicated into one Channel"""
        output = self._upgrade_and_validate(V1_DEDUP)

        channels = output["data_streams"][0]["configurations"][0]["channels"]
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]["channel_name"], "488")

        # But both tiles are still preserved as images
        images = output["data_streams"][0]["configurations"][0]["images"]
        self.assertEqual(len(images), 2)


if __name__ == "__main__":
    unittest.main()
