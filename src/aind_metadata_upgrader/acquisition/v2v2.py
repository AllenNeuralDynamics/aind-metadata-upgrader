"""2.x to 2.x acquisition upgrade functions"""

import re
from typing import Optional

from aind_data_schema.core.acquisition import AcquisitionSubjectDetails

from aind_metadata_upgrader.base import CoreUpgrader


def _parse_repr_transform(s: str) -> Optional[dict]:
    """Parse a Python repr-style transform string into a dict.

    Handles forms like:
      "object_type='Scale' scale=[512.0, 512.0]"
      "object_type='Translation' translation=[-1216.0, -378.0]"
    """
    if not isinstance(s, str):
        return None
    ot_match = re.search(r"object_type='([^']+)'", s)
    if not ot_match:
        return None
    object_type = ot_match.group(1)
    result: dict = {"object_type": object_type}
    for key in ("scale", "translation", "rotation", "matrix"):
        arr_match = re.search(rf"{key}=\[([^\]]*)\]", s)
        if arr_match:
            try:
                result[key] = [float(x.strip()) for x in arr_match.group(1).split(",") if x.strip()]
            except ValueError:
                pass
    return result


class AcquisitionUpgraderV2V2(CoreUpgrader):
    """Upgrade acquisition core file within the 2.x series"""

    def _upgrade_calibrations(self, data: dict) -> dict:
        """Rename deprecated calibration object_type values"""
        calibrations = data.get("calibrations", [])
        if not calibrations:
            return data

        for calibration in calibrations:
            if calibration.get("object_type") == "Laser calibration":
                calibration["object_type"] = "Power calibration"
                calibration["description"] = "Power measured for various power or percentage input strengths"

        data["calibrations"] = calibrations
        return data

    def _upgrade_experimenters(self, data: dict) -> dict:
        """Convert experimenter objects to strings (ORCID or name)"""
        experimenters = data.get("experimenters", [])
        if not experimenters:
            return data

        upgraded = []
        for experimenter in experimenters:
            if isinstance(experimenter, dict):
                # Prefer registry_identifier (e.g. ORCID), fall back to name
                identifier = experimenter.get("registry_identifier") or experimenter.get("name")
                if identifier:
                    upgraded.append(str(identifier))
            else:
                upgraded.append(experimenter)

        data["experimenters"] = upgraded
        return data

    def _upgrade_subject_details(self, data: dict) -> dict:
        """Create default subject_details if missing or null"""
        if not data.get("subject_details"):
            data["subject_details"] = AcquisitionSubjectDetails(
                mouse_platform_name="unknown",
            ).model_dump()
        return data

    def _repair_imaging_config_transforms(self, data: dict) -> dict:
        """Convert repr-string transform/dimension fields in ImagingConfig images to dicts.

        Old data sometimes stored Scale/Translation objects as their Python repr strings.
        """
        for stream in data.get("data_streams", []):
            if not isinstance(stream, dict):
                continue
            for config in stream.get("configurations", []):
                if not isinstance(config, dict) or config.get("object_type") != "Imaging config":
                    continue
                for image in config.get("images", []):
                    if not isinstance(image, dict):
                        continue
                    if isinstance(image.get("dimensions"), str):
                        parsed = _parse_repr_transform(image["dimensions"])
                        if parsed:
                            image["dimensions"] = parsed
                    transforms = image.get("image_to_acquisition_transform")
                    if isinstance(transforms, list):
                        image["image_to_acquisition_transform"] = [
                            _parse_repr_transform(t) if isinstance(t, str) else t
                            for t in transforms
                        ]
        return data

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the acquisition data within the 2.x series"""
        data = self._upgrade_calibrations(data)
        data = self._upgrade_experimenters(data)
        data = self._upgrade_subject_details(data)
        data = self._repair_imaging_config_transforms(data)
        data["schema_version"] = schema_version
        return data
