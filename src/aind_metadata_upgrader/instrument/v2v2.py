"""2.x to 2.x instrument upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader


class InstrumentUpgraderV2V2(CoreUpgrader):
    """Upgrade instrument core file within the 2.x series"""

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

    def _upgrade_components(self, data: dict) -> dict:
        """Fix component fields that changed format in the 2.x series"""
        components = data.get("components", [])
        if not components:
            return data

        for component in components:
            # Fix manufacturer.registry: dict -> enum string "{name} ({abbreviation})"
            manufacturer = component.get("manufacturer")
            if isinstance(manufacturer, dict):
                registry = manufacturer.get("registry")
                if isinstance(registry, dict):
                    name = registry.get("name", "")
                    abbreviation = registry.get("abbreviation", "")
                    if name and abbreviation:
                        manufacturer["registry"] = f"{name} ({abbreviation})"
                    else:
                        manufacturer["registry"] = None

            # Fix bin_mode: "None" string -> "No binning" (the field default)
            if component.get("bin_mode") == "None":
                component["bin_mode"] = "No binning"

        data["components"] = components
        return data

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the instrument data within the 2.x series"""
        data = self._upgrade_calibrations(data)
        data = self._upgrade_components(data)
        data["schema_version"] = schema_version
        return data
