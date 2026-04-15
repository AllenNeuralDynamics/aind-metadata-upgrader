"""2.x to 2.x acquisition upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader


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

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the acquisition data within the 2.x series"""
        data = self._upgrade_calibrations(data)
        data = self._upgrade_experimenters(data)
        data["schema_version"] = schema_version
        return data
