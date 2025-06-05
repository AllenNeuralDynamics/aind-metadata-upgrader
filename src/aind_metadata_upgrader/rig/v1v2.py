"""<=v1.4 to v2.0 rig upgrade functions"""

import re
from datetime import date
from typing import Optional

from aind_data_schema.components.coordinates import (
    Axis,
    AxisName,
    CoordinateSystem,
    CoordinateSystemLibrary,
    Direction,
    Origin,
)
from aind_data_schema.components.devices import Device
from aind_data_schema.components.measurements import (
    PowerCalibration,
    VolumeCalibration,
)
from aind_data_schema.core.instrument import (
    Connection,
    ConnectionData,
    ConnectionDirection,
)
from aind_data_schema_models.units import (
    PowerUnit,
    SizeUnit,
    TimeUnit,
    VolumeUnit,
)

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.rig.v1v2_devices import (
    saved_connections,
    upgrade_camera_assembly,
    upgrade_daq_devices,
    upgrade_detector,
    upgrade_ephys_assembly,
    upgrade_fiber_assembly,
    upgrade_fiber_patch_cord,
    upgrade_laser_assembly,
    upgrade_mouse_platform,
    upgrade_stimulus_device,
    upgrade_dmd,
    upgrade_polygonal_scanner,
    upgrade_pockels_cell,
)
from aind_metadata_upgrader.utils.v1v2_utils import (
    upgrade_enclosure,
    upgrade_light_source,
    upgrade_objective,
    upgrade_v1_modalities,
    upgrade_lens,
    upgrade_filter,
    basic_device_checks,
)

BREGMA_ALS = CoordinateSystem(
    name="BREGMA_ALS",
    origin=Origin.BREGMA,
    axis_unit=SizeUnit.UM,
    axes=[
        Axis(name=AxisName.X, direction=Direction.PA),  # X towards nose (posterior to anterior)
        Axis(name=AxisName.Y, direction=Direction.RL),  # Y by right-hand rule (right to left)
        Axis(name=AxisName.Z, direction=Direction.DU),  # Z up (down to up)
    ],
)


class RigUpgraderV1V2(CoreUpgrader):
    """Upgrade rig core file from v1.x to v2.0"""

    def _parse_name(self, data: dict):
        """Pull the rig_id and location from the rig_id field"""

        instrument_id = data.get("rig_id", "")
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
                    raise ValueError(f"Rig ID '{instrument_id}' does not match expected format")

        # If the rig_id didn't match the regex, we just keep it as-is
        return instrument_id, location

    def _get_coordinate_system(self, data: dict) -> Optional[dict]:
        """Pull coordinate system information"""

        origin = data.get("origin", None)
        rig_axes = data.get("rig_axes", None)

        if not origin and not rig_axes:
            return CoordinateSystemLibrary.BREGMA_ARI.model_dump()
        else:
            # We need to interpret the user's coordinate system (good luck to us)

            if (
                rig_axes
                and "lays on the Mouse Sagittal Plane, Positive direction is towards the nose of the mouse"
                in rig_axes[0]["direction"]
                and "positive pointing UP opposite the direction from the force of gravity" in rig_axes[1]["direction"]
                and "defined by the right hand rule and the other two axis" in rig_axes[2]["direction"]
            ):
                return BREGMA_ALS.model_dump()
            raise NotImplementedError("todo")

    def _get_calibration(self, data: dict) -> Optional[dict]:
        """Pull calibration information"""

        if "Water calibration" in data.get("description", ""):
            # Water calibration, we can handle this

            # drop empty calibratoins
            if not data["input"]["valve open time (s):"] and not data["output"]["water volume (ul):"]:
                return None

            calibration = VolumeCalibration(
                calibration_date=data["calibration_date"],
                device_name=data["device_name"],
                input=data["input"]["valve open time (s):"],
                input_unit=TimeUnit.S,
                output=data["output"]["water volume (ul):"],
                output_unit=VolumeUnit.UL,
                notes=(
                    data["notes"]
                    if data["notes"]
                    else "" + " (v1v2 upgrade): Liquid calibration upgraded from v1.x format."
                ),
            )
        elif "laser power calibration" in data.get("description", "").lower() and "power_setting" in data.get(
            "input", {}
        ):
            # Laser calibration, may or may not have data

            # Drop empty calibrations
            if not data["input"]["power_setting"] and not data["output"]["power_output"]:
                return None

            calibration = PowerCalibration(
                calibration_date=data["calibration_date"],
                device_name=data["device_name"],
                input=data["input"]["power_setting"],
                input_unit=PowerUnit.PERCENT,
                output=data["output"]["power_output"],
                output_unit=PowerUnit.MW,
            )
        elif "laser power calibration" in data.get("description", "").lower() and "power percent" in data.get(
            "input", {}
        ):
            # Laser calibration, may or may not have data

            # Drop empty calibrations
            if not data["input"]["power percent"] and not data["output"]["power mW"]:
                return None

            calibration = PowerCalibration(
                calibration_date=data["calibration_date"],
                device_name=data["device_name"],
                input=data["input"]["power percent"],
                input_unit=PowerUnit.PERCENT,
                output=data["output"]["power mW"],
                output_unit=PowerUnit.MW,
            )
        elif "led calibration" in data.get("description", "").lower():
            # LED calibration, may or may not have data

            if not data["input"]["Power setting"] and not data["output"]["Power mW"]:
                return None

            calibration = PowerCalibration(
                calibration_date=data["calibration_date"],
                device_name=data["device_name"],
                input=data["input"]["Power setting"],
                input_unit=PowerUnit.PERCENT,
                output=data["output"]["Power mW"],
                output_unit=PowerUnit.MW,
            )
        else:
            raise ValueError(f"Unsupported calibration: {data}")

        return calibration.model_dump() if calibration else None

    def _none_to_list(self, devices: Optional[list]) -> list:
        """Upgrade a device to it's new device model"""

        if not devices:
            return []

        return devices

    def _get_components_connections(self, data: dict) -> tuple[Optional[list], list]:
        """Pull components from data"""

        mouse_platform = data.get("mouse_platform", None)
        mouse_platform = upgrade_mouse_platform(mouse_platform) if mouse_platform else None

        stimulus_devices = data.get("stimulus_devices", [])
        stimulus_devices = self._none_to_list(stimulus_devices)
        stimulus_devices = [upgrade_stimulus_device(device) for device in stimulus_devices]

        camera_assemblies = data.get("cameras", [])
        camera_assemblies = self._none_to_list(camera_assemblies)
        camera_assemblies = [upgrade_camera_assembly(device) for device in camera_assemblies]

        enclosure = data.get("enclosure", None)
        enclosure = upgrade_enclosure(enclosure) if enclosure else None

        ephys_assemblies = data.get("ephys_assemblies", [])
        ephys_assemblies = self._none_to_list(ephys_assemblies)
        ephys_assemblies = [upgrade_ephys_assembly(assembly) for assembly in ephys_assemblies]

        fiber_assemblies = data.get("fiber_assemblies", [])
        fiber_assemblies = self._none_to_list(fiber_assemblies)
        fiber_assemblies = [upgrade_fiber_assembly(assembly) for assembly in fiber_assemblies]

        stick_microscopes = data.get("stick_microscopes", [])
        stick_microscopes = self._none_to_list(stick_microscopes)
        stick_microscopes = [upgrade_camera_assembly(scope) for scope in stick_microscopes]

        laser_assemblies = data.get("laser_assemblies", [])
        laser_assemblies = self._none_to_list(laser_assemblies)
        laser_assemblies = [upgrade_laser_assembly(assembly) for assembly in laser_assemblies]

        patch_cords = data.get("patch_cords", [])
        patch_cords = self._none_to_list(patch_cords)
        patch_cords = [upgrade_fiber_patch_cord(cord) for cord in patch_cords]

        light_sources = data.get("light_sources", [])
        light_sources = self._none_to_list(light_sources)
        light_sources = [upgrade_light_source(source) for source in light_sources]

        detectors = data.get("detectors", [])
        detectors = self._none_to_list(detectors)
        detectors = [upgrade_detector(detector) for detector in detectors]

        objectives = data.get("objectives", [])
        objectives = self._none_to_list(objectives)
        objectives = [upgrade_objective(obj) for obj in objectives]

        filters = data.get("filters", [])
        filters = self._none_to_list(filters)
        filters = [upgrade_filter(filt) for filt in filters]

        lenses = data.get("lenses", [])
        lenses = self._none_to_list(lenses)
        lenses = [upgrade_lens(lens) for lens in lenses]

        dmds = data.get("dmds", [])
        dmds = self._none_to_list(dmds)
        dmds = [upgrade_dmd(dmd) for dmd in dmds]

        polygonal_scanners = data.get("polygonal_scanners", [])
        polygonal_scanners = self._none_to_list(polygonal_scanners)
        polygonal_scanners = [upgrade_polygonal_scanner(scanner) for scanner in polygonal_scanners]

        pockels_cells = data.get("pockels_cells", [])
        pockels_cells = self._none_to_list(pockels_cells)
        pockels_cells = [upgrade_pockels_cell(cell) for cell in pockels_cells]

        additional_devices = data.get("additional_devices", [])
        additional_devices = self._none_to_list(additional_devices)
        additional_devices = [basic_device_checks(device, "Device") for device in additional_devices]

        daqs = self._none_to_list(data.get("daqs", []))
        daqs = [upgrade_daq_devices(daq) for daq in daqs]
        del data["daqs"]

        # Compile components list
        components = [
            mouse_platform,
            *stimulus_devices,
            *camera_assemblies,
            *daqs,
            *ephys_assemblies,
            *fiber_assemblies,
            *stick_microscopes,
            *laser_assemblies,
            *patch_cords,
            *light_sources,
            *detectors,
            *objectives,
            *filters,
            *lenses,
            *dmds,
            *polygonal_scanners,
            *pockels_cells,
            *additional_devices,
        ]
        if enclosure:
            components.append(enclosure)

        # # Handle connections and upgrade DAQDevice to new version

        # print(f"{len(saved_connections)} saved connections pending")
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

        # # Check that we're going to pass the connection validation
        # # Flatten the list of device names from all connections
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
        """Upgrade the rig core file data to a v2.0 instrument"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        instrument_id, location = self._parse_name(data)
        modification_date = data.get("modification_date", date.today())
        modalities = upgrade_v1_modalities(data)
        temperature_control = data.get("temperature_control", None)
        coordinate_system = self._get_coordinate_system(data)
        notes = data.get("notes", "")

        calibrations = [self._get_calibration(cal) for cal in data.get("calibrations", [])]
        # remove None values from calibrations list
        calibrations = [cal for cal in calibrations if cal is not None]

        components, connections = self._get_components_connections(data)

        return {
            "object_type": "Instrument",
            "schema_version": schema_version,
            "instrument_id": instrument_id,
            "location": location,
            "modification_date": modification_date,
            "modalities": modalities,
            "temperature_control": temperature_control,
            "calibrations": calibrations,
            "coordinate_system": coordinate_system,
            "components": components,
            "connections": connections,
            "notes": notes,
        }
