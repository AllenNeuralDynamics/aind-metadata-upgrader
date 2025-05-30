"""<=v1.4 to v2.0 instrument upgrade functions"""

from typing import Optional
import re
from datetime import date

from aind_metadata_upgrader.base import CoreUpgrader

from aind_data_schema.components.measurements import Calibration
from aind_data_schema.components.coordinates import CoordinateSystemLibrary

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.units import SizeUnit


class InstrumentUpgraderV1V2(CoreUpgrader):
    """Upgrade instrument core file from v1.x to v2.0"""

    def _parse_name(self, data: dict):
        """Pull the instrument_id and location from the instrument_id field"""

        instrument_id = data.get("instrument_id", "")
        location = data.get("location", None)  # Default location to None

        if not location:
            id_regex = re.compile("^[a-zA-Z0-9]+_[a-zA-Z0-9]+_\d{4}-\d{2}-\d{2}$")
            match = re.search(id_regex, instrument_id)
            if match:
                parts = instrument_id.split("_")
                if len(parts) == 3:
                    location = parts[0]
                    instrument_id = parts[1]
                else:
                    raise ValueError(f"Instrument ID '{instrument_id}' does not match expected format")

        # If the insturment_id didn't match the regex, we just keep it as-is
        return instrument_id, location

    def _get_modalities(self, data: dict) -> list:
        modalities = []
        instrument_type = data.get("instrument_type", None)
        if not instrument_type:
            # Try to get it from the "type" field
            instrument_type = data.get("type", None)
            if not instrument_type:
                raise ValueError("Instrument type is required")
        else:
            if instrument_type == "confocal":
                modalities.append(Modality.CONFOCAL.model_dump())
            if instrument_type == "diSPIM" or instrument_type == "exaSPIM" or instrument_type == "mesoSPIM" or instrument_type == "smartSPIM":
                modalities.append(Modality.SPIM.model_dump())
            if instrument_type == "Two photon":
                modalities.append(Modality.POPHYS.model_dump())
            if instrument_type == "ecephys":
                modalities.append(Modality.ECEPHYS.model_dump())
            if instrument_type == "Other":
                raise ValueError("Instrument type 'Other' is not supported. Please specify a valid instrument type.")

        return modalities

    def _get_calibration(self, data: dict) -> Optional[list]:
        """Pull calibration information

        Note that calibrations for instruments had to point to files, so the best we can do is put the data
        into an empty calibration object with a note pointing to the file."""

        if data.get("calibration_data", None):
            # We have a calibration, wrap it in the new Calibration object
            return [Calibration(
                calibration_date=data.get("calibration_date"),
                device_name=data.get("instrument_id"),
                input=[],
                output=[],
                input_unit=SizeUnit.UM,
                output_unit=SizeUnit.UM,
                description="Calibration data from v1.x instrument, see notes for file path.",
                notes=data.get("calibration_data"),
            ).model_dump()]

        return None

    def _get_coordinate_system(self, data: dict) -> Optional[dict]:
        """Pull coordinate system information"""

        return CoordinateSystemLibrary.BREGMA_ARI.model_dump()

    def _upgrade_devices(self, devices: list, object_type: str) -> list:
        """Upgrade a device to it's new device model"""

        if not devices:
            return []

        for i, device in enumerate(devices):
            device["object_type"] = object_type

            if "name" not in device or not device["name"]:
                device["name"] = f"{object_type} {i+1}"

            devices[i] = device

        return devices

    def _get_components_connections(self, data: dict) -> Optional[list]:
        """Pull components from data"""

        # Note we are ignoring optical_tables, which are gone
        enclosure = data.get("enclosure", None)
        if enclosure:
            enclosure["object_type"] = "Enclosure"

        objectives = data.get("objectives", [])
        objectives = self._upgrade_devices(objectives, "Objective")
        detectors = data.get("detectors", [])
        detectors = self._upgrade_devices(detectors, "Detector")
        light_sources = data.get("light_sources", [])
        light_sources = self._upgrade_devices(light_sources, "Light source")
        lenses = data.get("lenses", [])
        lenses = self._upgrade_devices(lenses, "Lens")
        fluorescence_filters = data.get("fluorescence_filters", [])
        fluorescence_filters = self._upgrade_devices(fluorescence_filters, "Fluorescence filter")
        motorized_stages = data.get("motorized_stages", [])
        motorized_stages = self._upgrade_devices(motorized_stages, "Motorized stage")
        scanning_stages = data.get("scanning_stages", [])
        scanning_stages = self._upgrade_devices(scanning_stages, "Scanning stage")
        additional_devices = data.get("additional_devices", [])
        additional_devices = self._upgrade_devices(additional_devices, "Device")

        print(f"All devices: {objectives + detectors + light_sources + lenses + fluorescence_filters + motorized_stages + scanning_stages + additional_devices}")

        com_ports = data.get("com_ports", [])
        daqs = data.get("daqs", [])

        # Compile all components, make sure to add object_type fields

        # Handle connections and upgrade DAQDevice to new version

        return []

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the subject core file data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        instrument_id, location = self._parse_name(data)
        modification_date = data.get("modification_date", date.today())
        modalities = self._get_modalities(data)
        temperature_control = data.get("temperature_control", None)
        calibrations = self._get_calibration(data)
        coordinate_system = self._get_coordinate_system(data)
        components = self._get_components_connections(data)

        # Fields we are removing
        # optical_tables

        return {
            "object_type": "Instrument",
            "instrument_id": instrument_id,
            "location": location,
            "modification_date": modification_date,
            "modalities": modalities,
            "temperature_control": temperature_control,
            "calibrations": calibrations,
            "coordinate_system": coordinate_system,
            "components": components,
        }
