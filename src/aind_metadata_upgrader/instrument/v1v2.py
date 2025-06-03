"""<=v1.4 to v2.0 instrument upgrade functions"""

from typing import Optional
import re
from datetime import date

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.instrument.v1v2_devices import (
    upgrade_enclosure,
    upgrade_objective,
    upgrade_detector,
    upgrade_light_source,
    upgrade_lenses,
    upgrade_fluorescence_filters,
    upgrade_motorized_stages,
    upgrade_scanning_stages,
    upgrade_additional_devices,
    upgrade_daq_devices,
    saved_connections,
)

from aind_data_schema.components.measurements import Calibration
from aind_data_schema.components.coordinates import CoordinateSystemLibrary
from aind_data_schema.components.devices import Microscope, Device
from aind_data_schema.core.instrument import Connection, ConnectionData, ConnectionDirection

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.units import SizeUnit


class InstrumentUpgraderV1V2(CoreUpgrader):
    """Upgrade instrument core file from v1.x to v2.0"""

    def _parse_name(self, data: dict):
        """Pull the instrument_id and location from the instrument_id field"""

        instrument_id = data.get("instrument_id", "")
        location = data.get("location", None)  # Default location to None

        if not location:
            id_regex = re.compile(r"^[a-zA-Z0-9]+_[a-zA-Z0-9]+_\d{4}-\d{2}-\d{2}$")
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
            if (
                instrument_type == "diSPIM"
                or instrument_type == "exaSPIM"
                or instrument_type == "mesoSPIM"
                or instrument_type == "smartSPIM"
            ):
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
            return [
                Calibration(
                    calibration_date=data.get("calibration_date"),
                    device_name=data.get("instrument_id"),
                    input=[],
                    output=[],
                    input_unit=SizeUnit.UM,
                    output_unit=SizeUnit.UM,
                    description="Calibration data from v1.x instrument, see notes for file path.",
                    notes=data.get("calibration_data"),
                ).model_dump()
            ]

        return None

    def _get_coordinate_system(self, data: dict) -> Optional[dict]:
        """Pull coordinate system information"""

        return CoordinateSystemLibrary.BREGMA_ARI.model_dump()

    def _none_to_list(self, devices: Optional[list]) -> list:
        """Upgrade a device to it's new device model"""

        if not devices:
            return []

        return devices

    def _get_components_connections(self, data: dict) -> tuple[Optional[list], list]:
        """Pull components from data"""

        # Note we are ignoring optical_tables, which are gone
        enclosure = data.get("enclosure", None)
        enclosure = upgrade_enclosure(enclosure) if enclosure else None

        objectives = data.get("objectives", [])
        objectives = self._none_to_list(objectives)
        objectives = [upgrade_objective(objective) for objective in objectives]

        detectors = data.get("detectors", [])
        detectors = self._none_to_list(detectors)
        detectors = [upgrade_detector(detector) for detector in detectors]

        light_sources = data.get("light_sources", [])
        light_sources = self._none_to_list(light_sources)
        light_sources = [upgrade_light_source(light_source) for light_source in light_sources]

        lenses = data.get("lenses", [])
        lenses = self._none_to_list(lenses)
        lenses = [upgrade_lenses(lens) for lens in lenses]

        fluorescence_filters = data.get("fluorescence_filters", [])
        fluorescence_filters = self._none_to_list(fluorescence_filters)
        fluorescence_filters = [upgrade_fluorescence_filters(filter_device) for filter_device in fluorescence_filters]

        motorized_stages = data.get("motorized_stages", [])
        motorized_stages = self._none_to_list(motorized_stages)
        motorized_stages = [upgrade_motorized_stages(stage) for stage in motorized_stages]

        scanning_stages = data.get("scanning_stages", [])
        scanning_stages = self._none_to_list(scanning_stages)
        scanning_stages = [upgrade_scanning_stages(stage) for stage in scanning_stages]

        additional_devices = data.get("additional_devices", [])
        additional_devices = self._none_to_list(additional_devices)
        additional_devices = [upgrade_additional_devices(device) for device in additional_devices]

        # Create the new Microscope device
        microscope = Microscope(
            name=data.get("instrument_id", "Microscope"),
        )
        scope_name = microscope.name

        com_ports = data.get("com_ports", [])
        for port in com_ports:
            saved_connections.append(
                {
                    "receive": port["hardware_name"],
                    "send": scope_name,
                }
            )
        del data["com_ports"]

        daqs = self._none_to_list(data.get("daqs", []))
        daqs = [upgrade_daq_devices(daq) for daq in daqs]
        del data["daqs"]

        # Compile components list
        components = [
            *objectives,
            *detectors,
            *light_sources,
            *lenses,
            *fluorescence_filters,
            *motorized_stages,
            *scanning_stages,
            *additional_devices,
            *daqs,
            microscope.model_dump(),
        ]
        if enclosure:
            components.append(enclosure)

        # Handle connections and upgrade DAQDevice to new version

        print(f"{len(saved_connections)} saved connections pending")
        connections = []

        for connection in saved_connections:
            # Check if this is just a model_dump of a Connection object
            if "device_names" in connection:
                connections.append(connection)
            else:
                connections.append(
                    Connection(
                        device_names=[connection["send"], connection["receive"]],
                        connection_data={
                            connection["send"]: ConnectionData(
                                direction=ConnectionDirection.SEND,
                            ),
                            connection["receive"]: ConnectionData(
                                direction=ConnectionDirection.RECEIVE,
                            ),
                        },
                    ).model_dump()
                )

        # Check that we're going to pass the connection validation
        # Flatten the list of device names from all connections
        connection_names = [name for conn in connections for name in conn["device_names"]]
        component_names = [comp["name"] for comp in components]

        for name in connection_names:
            if name not in component_names:
                # Create an empty Device with the name
                device = Device(
                    name=name,
                    notes="(v1v2 upgrade) This device was not found in the components list, but is referenced in connections.",
                )
                components.append(device.model_dump())

        return (components, connections)

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
        components, connections = self._get_components_connections(data)

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
            "connections": connections,
        }
