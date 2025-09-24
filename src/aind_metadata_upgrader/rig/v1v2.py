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
from aind_data_schema.components.connections import (
    Connection,
)
from aind_data_schema_models.units import SizeUnit

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.rig.v1v2_devices import (
    upgrade_camera_assembly,
    upgrade_daq_devices,
    upgrade_detector,
    upgrade_dmd,
    upgrade_ephys_assembly,
    upgrade_fiber_assembly,
    upgrade_fiber_patch_cord,
    upgrade_laser_assembly,
    upgrade_mouse_platform,
    upgrade_pockels_cell,
    upgrade_polygonal_scanner,
    upgrade_stimulus_device,
)
from aind_metadata_upgrader.utils.v1v2_utils import (
    upgrade_calibration,
    upgrade_enclosure,
    upgrade_filter,
    upgrade_generic_device,
    upgrade_lens,
    upgrade_light_source,
    upgrade_objective,
    upgrade_v1_modalities,
)
from aind_data_schema.components.devices import CameraTarget
from aind_metadata_upgrader.utils.validators import recursive_get_all_names

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

    def __init__(self):
        """Init"""
        super().__init__()

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
            elif (
                origin == "Bregma"
                and rig_axes
                and "towards the nose of the mouse" in rig_axes[0]["direction"]
                and "away from the nose of the mouse" in rig_axes[1]["direction"]
                and "Positive pointing up" in rig_axes[2]["direction"]
            ):
                # This appears to be a Bregma coordinate system with:
                # X: towards nose (posterior to anterior)
                # Y: away from nose (possibly right to left, but ambiguous)
                # Z: up
                # We'll assume this matches BREGMA_ALS based on the X and Z definitions
                # this is probably an older version of the same SIPE CS
                return BREGMA_ALS.model_dump()
            else:
                print((origin, rig_axes))
                raise NotImplementedError("todo")

    def _none_to_list(self, devices: Optional[list]) -> list:
        """Upgrade a device to it's new device model"""

        if not devices:
            return []

        return devices

    def _upgrade_primary_devices(self, data: dict) -> tuple[dict, list, list]:
        """Upgrade primary devices like mouse platform and stimulus devices"""
        all_connections = []

        # Mouse platform
        mouse_platform = data.get("mouse_platform", None)
        if mouse_platform:
            mouse_platform_data, mouse_platform_connections = upgrade_mouse_platform(mouse_platform)
            mouse_platform = mouse_platform_data
            all_connections.extend(mouse_platform_connections)
        else:
            mouse_platform = None

        # Stimulus devices
        stimulus_devices = data.get("stimulus_devices", [])
        if isinstance(stimulus_devices, dict):
            stimulus_devices = [stimulus_devices]
        stimulus_devices = self._none_to_list(stimulus_devices)

        upgraded_stimulus_devices, stimulus_connections = self._upgrade_devices_with_connections(
            stimulus_devices, upgrade_stimulus_device
        )
        all_connections.extend(stimulus_connections)

        return mouse_platform, upgraded_stimulus_devices, all_connections

    def _upgrade_camera_and_imaging_devices(self, data: dict) -> tuple[list, list, list]:
        """Upgrade camera assemblies and imaging-related devices"""
        all_connections = []

        # Camera assemblies
        camera_assemblies = self._none_to_list(data.get("cameras", []))
        upgraded_camera_assemblies, camera_connections = self._upgrade_devices_with_connections(
            camera_assemblies, upgrade_camera_assembly
        )
        all_connections.extend(camera_connections)

        # Stick microscopes
        stick_microscopes = self._none_to_list(data.get("stick_microscopes", []))
        upgraded_stick_microscopes = []
        for scope in stick_microscopes:
            scope_data, scope_connections = upgrade_camera_assembly(scope)
            upgraded_stick_microscopes.append(scope_data)
            all_connections.extend(scope_connections)

        return upgraded_camera_assemblies, upgraded_stick_microscopes, all_connections

    def _upgrade_optical_components(self, data: dict) -> tuple[list, list, list, list, list, list]:
        """Upgrade optical components like objectives, filters, lenses"""
        objectives = self._none_to_list(data.get("objectives", []))
        objectives = [upgrade_objective(obj) for obj in objectives]

        filters = self._none_to_list(data.get("filters", []))
        filters = [upgrade_filter(filt) for filt in filters]

        lenses = self._none_to_list(data.get("lenses", []))
        lenses = [upgrade_lens(lens) for lens in lenses]

        dmds = self._none_to_list(data.get("dmds", []))
        dmds = [upgrade_dmd(dmd) for dmd in dmds]

        polygonal_scanners = self._none_to_list(data.get("polygonal_scanners", []))
        polygonal_scanners = [upgrade_polygonal_scanner(scanner) for scanner in polygonal_scanners]

        pockels_cells = self._none_to_list(data.get("pockels_cells", []))
        pockels_cells = [upgrade_pockels_cell(cell) for cell in pockels_cells]

        return objectives, filters, lenses, dmds, polygonal_scanners, pockels_cells

    def _upgrade_ephys_and_fiber_devices(self, data: dict) -> tuple[list, list, list, list, list, list]:
        """Upgrade ephys assemblies and fiber-related devices"""
        all_connections = []

        # Ephys assemblies
        ephys_assemblies = self._none_to_list(data.get("ephys_assemblies", []))
        opto_lasers = []
        upgraded_ephys_assemblies = []
        for assembly in ephys_assemblies:
            upgraded_assembly, lasers, connections = upgrade_ephys_assembly(assembly)
            upgraded_ephys_assemblies.append(upgraded_assembly)
            all_connections.extend(connections)
            if lasers:
                opto_lasers.extend(lasers)

        # Fiber assemblies
        fiber_assemblies = self._none_to_list(data.get("fiber_assemblies", []))
        fiber_assemblies = [upgrade_fiber_assembly(assembly) for assembly in fiber_assemblies]

        # Laser assemblies and patch cords
        laser_assemblies = self._none_to_list(data.get("laser_assemblies", []))
        laser_assemblies = [upgrade_laser_assembly(assembly) for assembly in laser_assemblies]

        patch_cords = self._none_to_list(data.get("patch_cords", []))
        patch_cords = [upgrade_fiber_patch_cord(cord) for cord in patch_cords]

        return upgraded_ephys_assemblies, opto_lasers, fiber_assemblies, laser_assemblies, patch_cords, all_connections

    def _create_components_list(
        self,
        mouse_platform,
        stimulus_devices,
        camera_assemblies,
        upgraded_daqs,
        upgraded_ephys_assemblies,
        fiber_assemblies,
        stick_microscopes,
        laser_assemblies,
        patch_cords,
        light_sources,
        opto_lasers,
        upgraded_detectors,
        objectives,
        filters,
        lenses,
        dmds,
        polygonal_scanners,
        pockels_cells,
        additional_devices,
        enclosure,
    ) -> list:
        """Create the final components list"""
        components = [
            mouse_platform,
            *stimulus_devices,
            *camera_assemblies,
            *upgraded_daqs,
            *upgraded_ephys_assemblies,
            *fiber_assemblies,
            *stick_microscopes,
            *laser_assemblies,
            *patch_cords,
            *light_sources,
            *opto_lasers,
            *upgraded_detectors,
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
        return components

    def _validate_components_and_connections(self, components: list, all_connections: list) -> tuple[list, list]:
        """Validate and create connections, add missing components if needed"""
        # Handle connections
        connections = []
        for connection in all_connections:
            # Check if this is just a model_dump of a Connection object
            if "object_type" in connection:
                connections.append(connection)
            else:
                connections.append(
                    Connection(
                        source_device=connection["send"],
                        target_device=connection["receive"],
                    ).model_dump()
                )

        # Check that we're going to pass the connection validation
        # Flatten the list of device names from all connections
        connection_names = [name for conn in connections for name in [conn["source_device"], conn["target_device"]]]
        connection_names = list(set(connection_names))  # Unique names only

        component_names = []
        for component in components:
            if component is not None:  # Skip None components
                component_names.extend(recursive_get_all_names(component))
        component_names = [name for name in component_names if name is not None]

        missing_names = []
        for name in connection_names:
            if name not in component_names:
                missing_names.append(name)

        for name in set(missing_names):
            # Create an empty Device with the name
            device = Device(
                name=name,
                notes=(
                    "(v1v2 upgrade rig) This device was not found in the components list, "
                    "but is referenced in connections."
                ),
            )
            components.append(device.model_dump())

        return components, connections

    def _get_components_connections(self, data: dict) -> tuple[list, list]:
        """Pull components from data"""
        all_connections = []

        # Upgrade primary devices
        mouse_platform, stimulus_devices, primary_connections = self._upgrade_primary_devices(data)
        all_connections.extend(primary_connections)

        # Upgrade camera and imaging devices
        camera_assemblies, stick_microscopes, camera_connections = self._upgrade_camera_and_imaging_devices(data)
        all_connections.extend(camera_connections)

        # Upgrade enclosure
        enclosure = data.get("enclosure", None)
        enclosure = upgrade_enclosure(enclosure) if enclosure else None

        # Upgrade ephys and fiber devices
        (upgraded_ephys_assemblies, opto_lasers, fiber_assemblies, laser_assemblies, patch_cords, ephys_connections) = (
            self._upgrade_ephys_and_fiber_devices(data)
        )
        all_connections.extend(ephys_connections)

        # Upgrade light sources and detectors
        light_sources = self._none_to_list(data.get("light_sources", []))
        light_sources = [upgrade_light_source(source) for source in light_sources]

        detectors = self._none_to_list(data.get("detectors", []))
        upgraded_detectors, detector_connections = self._upgrade_devices_with_connections(detectors, upgrade_detector)
        all_connections.extend(detector_connections)

        # Upgrade optical components
        (objectives, filters, lenses, dmds, polygonal_scanners, pockels_cells) = self._upgrade_optical_components(data)

        # Upgrade additional devices and DAQs
        additional_devices = self._none_to_list(data.get("additional_devices", []))
        additional_devices = [upgrade_generic_device(device) for device in additional_devices]

        daqs = self._none_to_list(data.get("daqs", []))
        upgraded_daqs, daq_connections = self._upgrade_devices_with_connections(daqs, upgrade_daq_devices)
        all_connections.extend(daq_connections)
        del data["daqs"]

        # Create components list and validate connections
        components = self._create_components_list(
            mouse_platform,
            stimulus_devices,
            camera_assemblies,
            upgraded_daqs,
            upgraded_ephys_assemblies,
            fiber_assemblies,
            stick_microscopes,
            laser_assemblies,
            patch_cords,
            light_sources,
            opto_lasers,
            upgraded_detectors,
            objectives,
            filters,
            lenses,
            dmds,
            polygonal_scanners,
            pockels_cells,
            additional_devices,
            enclosure,
        )

        components, connections = self._validate_components_and_connections(components, all_connections)
        return (components, connections)

        # Compile components list
        components = [
            mouse_platform,
            *stimulus_devices,
            *camera_assemblies,
            *daqs,
            *upgraded_ephys_assemblies,
            *fiber_assemblies,
            *stick_microscopes,
            *laser_assemblies,
            *patch_cords,
            *light_sources,
            *opto_lasers,
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

        # Handle connections
        connections = []

        for connection in all_connections:
            # Check if this is just a model_dump of a Connection object
            if "object_type" in connection:
                connections.append(connection)
            else:
                connections.append(
                    Connection(
                        source_device=connection["send"],
                        target_device=connection["receive"],
                    ).model_dump()
                )

        # # Check that we're going to pass the connection validation
        # # Flatten the list of device names from all connections
        connection_names = [name for conn in connections for name in [conn["source_device"], conn["target_device"]]]
        connection_names = list(set(connection_names))  # Unique names only

        component_names = []
        for component in components:
            component_names.extend(recursive_get_all_names(component))
        component_names = [name for name in component_names if name is not None]

        missing_names = []
        for name in connection_names:
            if name not in component_names:
                missing_names.append(name)

        for name in set(missing_names):
            # Create an empty Device with the name
            device = Device(
                name=name,
                notes=(
                    "(v1v2 upgrade rig) This device was not found in the components list, "
                    "but is referenced in connections."
                ),
            )
            components.append(device.model_dump())

        return (components, connections)

    def _upgrade_devices_with_connections(self, devices: list, upgrade_func) -> tuple[list, list]:
        """Helper method to upgrade devices that return connections."""
        upgraded_devices = []
        all_connections = []
        for device in devices:
            device_data, device_connections = upgrade_func(device)
            upgraded_devices.append(device_data)
            all_connections.extend(device_connections)
        return upgraded_devices, all_connections

    def _upgrade_simple_devices(self, devices: list, upgrade_func) -> list:
        """Helper method to upgrade devices that don't return connections."""
        return [upgrade_func(device) for device in devices]

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the rig core file data to a v2.0 instrument"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        instrument_id, location = self._parse_name(data)
        modification_date = data.get("modification_date", date.today())
        modalities = upgrade_v1_modalities(data)
        temperature_control = data.get("temperature_control", None)
        coordinate_system = self._get_coordinate_system(data)
        notes = data.get("notes", "")

        calibrations = [upgrade_calibration(cal) for cal in data.get("calibrations", [])]
        # remove None values from calibrations list
        calibrations = [cal for cal in calibrations if cal is not None]

        components, connections = self._get_components_connections(data)

        # If any cameras are present with camera_target == Other we need to flag this in the notes
        if notes is None and components:
            for component in components:
                if "target" in component and component["target"] == CameraTarget.OTHER:
                    notes = notes if notes else "" + " (v1v2 upgrade) Some cameras have unknown targets."

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
