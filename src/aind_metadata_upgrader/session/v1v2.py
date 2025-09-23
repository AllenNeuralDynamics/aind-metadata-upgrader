"""<=v1.4 to v2.0 session upgrade functions"""

from datetime import datetime
from typing import Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from aind_data_schema.base import GenericModel
from aind_data_schema.components.configs import (
    Channel,
    CoupledPlane,
    DetectorConfig,
    EphysAssemblyConfig,
    LaserConfig,
    LightEmittingDiodeConfig,
    ManipulatorConfig,
    MISModuleConfig,
    MRIScan,
    MriScanSequence,
    PatchCordConfig,
    PlanarImage,
    PlanarImageStack,
    Plane,
    PowerFunction,
    ProbeConfig,
    ScanType,
    SlapAcquisitionType,
    SlapPlane,
    SpeakerConfig,
    TriggerType,
    ImagingConfig,
)
from aind_data_schema.components.coordinates import (
    Affine,
    CoordinateSystemLibrary,
    Scale,
    Translation,
)
from aind_data_schema.components.identifiers import Code, Software
from aind_data_schema.core.acquisition import (
    Acquisition,
    AcquisitionSubjectDetails,
    DataStream,
    PerformanceMetrics,
    StimulusEpoch,
)
from aind_data_schema.components.connections import (
    Connection,
)
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.stimulus_modality import StimulusModality
from aind_data_schema_models.units import (
    MassUnit,
    PowerUnit,
    SizeUnit,
    SoundIntensityUnit,
    TimeUnit,
    VolumeUnit,
)

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v1v2_utils import (
    remove,
    upgrade_calibration,
    upgrade_targeted_structure,
    validate_angle_unit,
)


class SessionV1V2(CoreUpgrader):
    """Upgrade session from v1.4 to v2.0 (acquisition)"""

    def _upgrade_experimenter_names(self, experimenter_names: List[str]) -> List[str]:
        """Convert experimenter full names to Person objects"""
        experimenters = []

        if isinstance(experimenter_names, str):
            experimenter_names = [experimenter_names]

        for name in experimenter_names:
            if name and name.strip():
                experimenters.append(name.strip())
        return experimenters

    def _upgrade_maintenance(self, maintenance: List[Dict]) -> List[Dict]:
        """Upgrade maintenance objects"""
        upgraded_maintenance = []
        if maintenance:
            for maint in maintenance:
                if maint:
                    upgraded_maintenance.append(maint)
        return upgraded_maintenance

    def _determine_acquisition_type(self, data: Dict) -> str:
        """Determine acquisition type from V1 session data"""
        session_type = data.get("session_type")
        if session_type:
            return session_type
        return "Session"

    def _upgrade_light_source_config(self, data: Dict) -> Union[Dict, None]:
        """Upgrade light source config from v1 to v2"""
        if not data:
            return None

        device_type = data.get("device_type")
        device_name = data.get("name", "Unknown Device")
        excitation_power = data.get("excitation_power")
        if not excitation_power and "laser_power" in data:
            excitation_power = data["laser_power"]
        power_unit = data.get("excitation_power_unit")
        if not power_unit and "laser_power_unit" in data:
            power_unit = data["laser_power_unit"]

        if device_type == "Laser" or "laser" in device_name.lower():
            return LaserConfig(
                device_name=device_name,
                wavelength=data.get("wavelength", 0),
                wavelength_unit=SizeUnit.NM,
                power=float(excitation_power) if excitation_power else None,
                power_unit=PowerUnit.MW if power_unit == "milliwatt" else PowerUnit.PERCENT,
            ).model_dump()
        elif device_type == "Light emitting diode" or "led" in device_name.lower():
            return LightEmittingDiodeConfig(
                device_name=device_name,
                power=float(excitation_power) if excitation_power else None,
                power_unit=PowerUnit.MW if power_unit == "milliwatt" else PowerUnit.PERCENT,
            ).model_dump()
        else:
            print(data)
            raise NotImplementedError(f"Light source device type '{device_type}' not supported in v2 upgrade")

    def _upgrade_detector_config(self, detector: Dict) -> Dict:
        """Upgrade detector config from v1 to v2"""
        exposure_time = detector.get("exposure_time", -1)
        return DetectorConfig(
            device_name=detector.get("name", "Unknown Detector"),
            exposure_time=float(exposure_time) if exposure_time else -1,
            exposure_time_unit=TimeUnit.MS,
            trigger_type=TriggerType.INTERNAL if detector.get("trigger_type") == "Internal" else TriggerType.EXTERNAL,
        ).model_dump()

    def _upgrade_ephys_module_to_configs(self, ephys_module: Dict) -> List[Dict]:
        """Convert ephys module to EphysAssemblyConfig and ManipulatorConfig"""
        configs = []

        # We are going to assume this is an MPM system, since that's all we
        # supported in v1.4 anyways

        # Build up the MPM config
        mis_config = MISModuleConfig(
            arc_angle=ephys_module.get("arc_angle", 0.0),
            module_angle=ephys_module.get("module_angle", 0.0),
            rotation_angle=ephys_module.get("rotation_angle", 0.0),
            angle_unit=validate_angle_unit(ephys_module.get("angle_unit", "degrees")),
            notes=ephys_module.get("notes", None),
        )

        # Create ManipulatorConfig for the manipulator/dome module
        # Get manipulator coordinates
        manipulator_coordinates = ephys_module.get("manipulator_coordinates", {})
        x = manipulator_coordinates.get("x", 0.0)
        y = manipulator_coordinates.get("y", 0.0)
        z = manipulator_coordinates.get("z", 0.0)

        manipulator_config = ManipulatorConfig(
            coordinate_system=CoordinateSystemLibrary.MPM_MANIP_RFB,
            local_axis_positions=Translation(
                translation=[x, y, z],
            ),
            device_name="unknown",  # Unfortunately manipulator names were not in v1.4
        )

        probes = ephys_module.get("ephys_probes", [])
        probe_configs = []

        anatomical_coordinates = ephys_module.get("anatomical_coordinates", {})
        if anatomical_coordinates:
            x = anatomical_coordinates.get("x", 0.0)
            y = anatomical_coordinates.get("y", 0.0)
            z = anatomical_coordinates.get("z", 0.0)
            # We have no idea what these correspond to, but most likely
            # they are in AP/ML/DV order and in micrometers. But we really don't know for sure.
            ap = x
            ml = y
            dv = z
        else:
            # If no anatomical coordinates, default to the CCF origin coordinate
            ap = -13000 / 2
            ml = -11400 / 2
            dv = -8000 / 2

        # Check that the micron ranges make sense
        if ap < (-13000 / 2) or ap > (13000 / 2):
            raise ValueError(f"AP coordinate {ap} is out of range for Bregma reference")
        if ml < (-11400 / 2) or ml > (11400 / 2):
            raise ValueError(f"ML coordinate {ml} is out of range for Bregma reference")
        if dv < (-8000 / 2) or dv > (8000 / 2):
            raise ValueError(f"DV coordinate {dv} is out of range for Bregma reference")

        # Check that the reference is bremga
        reference = ephys_module.get("anatomical_reference", None)
        if not reference or reference.lower() != "bregma":
            ValueError(f"Anatomical reference must be 'bregma', got '{reference}'")

        for probe in probes:
            probe_config = ProbeConfig(
                device_name=probe.get("name", "unknown"),
                primary_targeted_structure=upgrade_targeted_structure(
                    ephys_module.get("primary_targeted_structure", "unknown")
                ),
                coordinate_system=CoordinateSystemLibrary.PINPOINT_PROBE_RSAB,
                transform=[
                    Translation(
                        translation=[ap, dv, ml],
                    ),
                    # Technically there is a rotation, but we don't know how to
                    # convert here so we'll just leave it as is...
                ],
            )
            probe_configs.append(probe_config.model_dump())

        # Create EphysAssemblyConfig
        ephys_config = EphysAssemblyConfig(
            device_name=ephys_module.get("assembly_name", "unknown"),
            manipulator=manipulator_config,
            probes=probe_configs,
            modules=[mis_config],
        )
        configs.append(ephys_config.model_dump())

        return configs

    def _upgrade_detector_config_v2(self, data: Dict) -> Dict:
        """Upgrade detector config from v1 to v2 (alternative implementation)"""

        data["device_name"] = data.get("name", "Unknown Detector")
        remove(data, "name")

        if "exposure_time" not in data or data["exposure_time"] is None:
            data["exposure_time"] = 0
        if "trigger_type" not in data or data["trigger_type"] is None:
            data["trigger_type"] = TriggerType.INTERNAL

        return DetectorConfig(**data).model_dump()

    def _upgrade_fiber_connection_config(self, stream: Dict, fiber_connection: Dict) -> tuple:
        """Convert a single fiber connection config, return Channel, PatchCordConfig, Connection"""

        # First, gather the names of all the devices that are involved
        patch_cord_name = fiber_connection.get("patch_cord_name", "unknown")
        fiber_name = fiber_connection.get("fiber_name", "unknown")
        channel_data = fiber_connection.get("channel", {})

        if not channel_data or channel_data["channel_name"] == "disconnected":
            return None, []

        # Deal with the detector
        detector_name = channel_data.get("detector_name", None)
        detector_config = stream.get("detectors", [])
        # Find the matching detector config
        matching_detector = next((d for d in detector_config if d.get("name") == detector_name), None)
        if matching_detector:
            matching_detector = self._upgrade_detector_config(matching_detector)
        else:
            # No matching detector found... create a default one
            matching_detector = DetectorConfig(
                device_name=detector_name,
                exposure_time=-1,
                trigger_type=TriggerType.INTERNAL,
            ).model_dump()

        # Build the light source
        light_source_name = channel_data.get("light_source_name", None)
        light_sources = stream.get("light_sources", [])
        # Find the matching light source config
        matching_light_source = next((ls for ls in light_sources if ls.get("name") == light_source_name), None)
        if not matching_light_source:
            raise ValueError(f"Light source '{light_source_name}' not found in stream light sources")

        light_source_config = self._upgrade_light_source_config(matching_light_source)

        # Build the actual channel object
        # Note we don't care if multiple patch cords make the same channel,
        # we'll sort it out when they get returned

        channel = Channel(
            channel_name=channel_data.get("channel_name", "unknown"),
            intended_measurement=channel_data.get("intended_measurement", None),
            detector=matching_detector,
            additional_device_names=channel_data.get("additional_device_names", None),
            light_sources=[light_source_config] if light_source_config else [],
            # We don't know any of the filter data because it wasn't stored properly
            emission_wavelength=channel_data.get("emission_wavelength", None),
            emission_wavelength_unit=channel_data.get("emission_wavelength_unit", None),
        )

        # Build the PatchCordConfig
        patch_cord_config = PatchCordConfig(
            device_name=patch_cord_name,
            channels=[channel],
        ).model_dump()

        # Build the connections
        connections = []
        # Build the light source->patch cord connection
        light_fiber_conn = Connection(
            source_device=light_source_name,
            target_device=patch_cord_name,
        )
        # patch cord to fiber, send_and_receive:
        patch_fiber_conn = Connection(
            source_device=patch_cord_name,
            target_device=fiber_name,
            send_and_receive=True,
        )
        # Finally patch cord to detector
        patch_detector_conn = Connection(
            source_device=patch_cord_name,
            target_device=matching_detector["device_name"],
        )
        connections.append(light_fiber_conn.model_dump())
        connections.append(patch_fiber_conn.model_dump())
        connections.append(patch_detector_conn.model_dump())

        return patch_cord_config, connections

    def _upgrade_fiber(self, stream: Dict) -> tuple:
        """Convert all fiber data within a stream to the new Channel and PatchCordConfig format"""

        # First gather all the old FiberConnectionConfig objects
        fiber_connection_configs = stream.get("fiber_connections", [])
        fiber_modules = stream.get("fiber_modules", [])
        for module in fiber_modules:
            fiber_connection_configs.extend(module.get("fiber_connections", []))

        # For each FiberConnectionConfig, run the new upgrader which will create a
        # Channel, PatchCordConfig, and a Connection
        patchcord_configs = []
        all_connections = []
        for fiber_conn in fiber_connection_configs:
            patchcord_config, connections = self._upgrade_fiber_connection_config(stream, fiber_conn)
            if patchcord_config:
                patchcord_configs.append(patchcord_config)
                all_connections.extend(connections)

        return patchcord_configs, all_connections

    def _upgrade_ophys_fov_to_plane(self, fov: Dict) -> Dict:
        """Convert ophys FOV to Plane"""
        # Determine the targeted structure
        targeted_structure = upgrade_targeted_structure(fov.get("targeted_structure"))

        plane = Plane(
            depth=float(fov.get("imaging_depth", 0)),
            depth_unit=SizeUnit.UM,
            power=float(fov.get("power", 0)) if fov.get("power") else 0.0,
            power_unit=PowerUnit.PERCENT,
            targeted_structure=targeted_structure,
        ).model_dump()

        # Handle coupled FOVs
        if fov.get("coupled_fov_index") is not None:
            coupled_plane = CoupledPlane(
                depth=float(fov.get("imaging_depth", 0)),
                depth_unit=SizeUnit.UM,
                power=float(fov.get("power", 0)) if fov.get("power") else 0.0,
                power_unit=PowerUnit.PERCENT,
                targeted_structure=targeted_structure,
                plane_index=fov.get("index", 0),
                coupled_plane_index=fov.get("coupled_fov_index"),
                power_ratio=float(fov.get("power_ratio", 1.0)) if fov.get("power_ratio") else 1.0,
            ).model_dump()
            return coupled_plane

        return plane

    def _upgrade_slap_fov_to_plane(self, slap_fov: Dict) -> Dict:
        """Convert SLAP FOV to SlapPlane"""
        # Determine the targeted structure
        targeted_structure = slap_fov.get("targeted_structure")
        if isinstance(targeted_structure, dict):
            ccf_structure = targeted_structure
        else:
            ccf_structure = {"name": str(targeted_structure), "acronym": "Unknown", "id": "0"}

        session_type = slap_fov.get("session_type")
        acquisition_type = SlapAcquisitionType.PARENT if session_type == "Parent" else SlapAcquisitionType.BRANCH

        return SlapPlane(
            depth=float(slap_fov.get("imaging_depth", 0)),
            depth_unit=SizeUnit.UM,
            power=float(slap_fov.get("power", 0)) if slap_fov.get("power") else 0.0,
            power_unit=PowerUnit.PERCENT,
            targeted_structure=ccf_structure,
            dmd_dilation_x=slap_fov.get("dmd_dilation_x", 0),
            dmd_dilation_y=slap_fov.get("dmd_dilation_y", 0),
            dilation_unit=SizeUnit.PX,
            slap_acquisition_type=acquisition_type,
            target_neuron=slap_fov.get("target_neuron"),
            target_branch=slap_fov.get("target_branch"),
            path_to_array_of_frame_rates=slap_fov.get("path_to_array_of_frame_rates", ""),
        ).model_dump()

    def _upgrade_mri_scan_to_config(self, scan: Dict) -> Dict:
        """Convert MRI scan to MRIScan config"""
        primary = scan.get("primary_scan", False)
        if primary:
            # Upgrade the affine transform
            coordinate_system = CoordinateSystemLibrary.MRI_LPS
            vc_orientation = scan.get("vc_orientation", None)
            vc_position = scan.get("vc_position", None)
            if not vc_orientation or not vc_position:
                raise ValueError("Primary MRI scan must have 'vc_orientation' and 'vc_position' for primary scans")
            rotation = vc_orientation["rotation"]
            rotation = Affine(
                affine_transform=[
                    [float(rotation[0]), float(rotation[1]), float(rotation[2])],
                    [float(rotation[3]), float(rotation[4]), float(rotation[5])],
                    [float(rotation[6]), float(rotation[7]), float(rotation[8])],
                ]
            )
            translation = Translation(translation=vc_position["translation"])
            transform = [rotation, translation]

            # Get voxel size
            voxel_size = scan.get("voxel_sizes", {})
            resolution = Scale(
                scale=voxel_size["scale"],
            )
        else:
            coordinate_system = None
            transform = None
            resolution = None

        mri_scan = MRIScan(
            device_name=scan.get("mri_scanner", {}).get("name", "Unknown Scanner"),
            scan_index=scan.get("scan_index", 0),
            scan_type=(ScanType.SCAN_3D if scan.get("scan_type") == "3D Scan" else ScanType.SETUP),
            primary_scan=scan.get("primary_scan", True),
            scan_sequence_type=(
                MriScanSequence.RARE if scan.get("scan_sequence_type") == "RARE" else MriScanSequence.OTHER
            ),
            echo_time=scan.get("echo_time", 1.0),
            echo_time_unit=TimeUnit.MS,
            repetition_time=scan.get("repetition_time", 100.0),
            repetition_time_unit=TimeUnit.MS,
            subject_position=scan.get("subject_position", "unknown"),
            additional_scan_parameters=scan.get("additional_scan_parameters", {}),
            scan_coordinate_system=coordinate_system,
            scan_affine_transform=transform,
            resolution=resolution,
            resolution_unit=SizeUnit.MM,
        )

        return mri_scan.model_dump()

    def _determine_stream_modality(self, stream: Dict) -> Optional[str]:
        """Determine the primary imaging modality for a stream"""
        modalities = stream.get("stream_modalities", [])

        # Look for imaging modalities
        for mod in modalities:
            if isinstance(mod, dict):
                abbreviation = mod.get("abbreviation", "")
                if abbreviation in ["ophys", "pophys", "slap", "fib"]:
                    return abbreviation
        return None

    def _create_ophys_components(self, stream: Dict, light_sources: List, detectors: List) -> tuple:
        """Create channels and images for ophys/pophys modality"""
        # Check if we have ophys_fovs or stack_parameters
        if stream.get("ophys_fovs"):
            return self._create_ophys_fov_components(stream, light_sources, detectors)
        elif stream.get("stack_parameters"):
            return self._create_stack_components(stream, light_sources, detectors)
        else:
            return [], []

    def _create_ophys_fov_components(self, stream: Dict, light_sources: List, detectors: List) -> tuple:
        """Create channels and PlanarImage objects from ophys_fovs"""
        channels = []
        images = []

        if len(detectors) > 1:
            raise ValueError("Multiple detectors are not yet supported in ophys upgrade")

        channel = Channel(
            channel_name="Ophys Channel",
            detector=(
                self._upgrade_detector_config(detectors[0])
                if detectors
                else DetectorConfig(
                    device_name="Unknown Detector",
                    exposure_time=1.0,
                    exposure_time_unit=TimeUnit.MS,
                    trigger_type=TriggerType.INTERNAL,
                )
            ),
            light_sources=[self._upgrade_light_source_config(ls) for ls in light_sources],
        ).model_dump()
        channels.append(channel)

        for i, fov in enumerate(stream.get("ophys_fovs", [])):
            # Create plane and image
            plane = self._upgrade_ophys_fov_to_plane(fov)
            image = PlanarImage(
                planes=[plane], image_to_acquisition_transform=[], channel_name=channel["channel_name"]
            ).model_dump()
            images.append(image)

        return channels, images

    def _create_stack_components(self, stream: Dict, light_sources: List, detectors: List) -> tuple:
        """Create channels and PlanarImageStack objects from stack_parameters"""
        channels = []
        images = []

        stack_params = stream.get("stack_parameters", {})
        stack_channels = stack_params.get("channels", [])

        # Create a detector lookup for efficiency
        detector_lookup = {d.get("name"): d for d in detectors}
        light_source_lookup = {ls.get("name"): ls for ls in light_sources}

        for stack_channel in stack_channels:
            # Find matching detector
            detector_name = stack_channel.get("detector_name")
            detector_data = detector_lookup.get(detector_name)
            if detector_data:
                exposure_time = (
                    float(detector_data.get("exposure_time", -1)) if detector_data.get("exposure_time") else -1
                )
                trigger_type = (
                    TriggerType.INTERNAL if detector_data.get("trigger_type") == "Internal" else TriggerType.EXTERNAL
                )
                detector_config = DetectorConfig(
                    device_name=detector_data.get("name", "Unknown Detector"),
                    exposure_time=exposure_time,
                    exposure_time_unit=TimeUnit.MS,
                    trigger_type=trigger_type,
                )
            else:
                detector_config = DetectorConfig(
                    device_name=detector_name or "Unknown Detector",
                    exposure_time=-1,
                    exposure_time_unit=TimeUnit.MS,
                    trigger_type=TriggerType.INTERNAL,
                )

            # Find matching light source
            light_source_name = stack_channel.get("light_source_name")
            light_source_data = light_source_lookup.get(light_source_name)
            light_source_configs = []
            if light_source_data:
                light_source_config = self._upgrade_light_source_config(light_source_data)
                if light_source_config:
                    light_source_configs.append(light_source_config)

            # Create channel
            channel = Channel(
                channel_name=stack_channel.get("channel_name", "Unknown Channel"),
                detector=detector_config,
                light_sources=light_source_configs,
                emission_wavelength=stack_channel.get("emission_wavelength"),
                emission_wavelength_unit=stack_channel.get("emission_wavelength_unit"),
            )
            channels.append(channel.model_dump())

            # Create plane for the stack
            targeted_structure = upgrade_targeted_structure(stack_params.get("targeted_structure", "unknown"))

            plane = Plane(
                depth=float(stack_channel.get("start_depth", 0)),
                depth_unit=SizeUnit.UM,
                power=float(stack_channel.get("excitation_power", 0)),
                power_unit=PowerUnit.PERCENT,
                targeted_structure=targeted_structure,
            )

            ap = stack_channel.get("fov_coordinate_ap", 0)
            ml = stack_channel.get("fov_coordinate_ml", 0)
            transform = [Translation(translation=[ap, ml, 0])]

            # Create PlanarImageStack
            image = PlanarImageStack(
                channel_name=stack_channel.get("channel_name", "Unknown Channel"),
                planes=[plane],
                image_to_acquisition_transform=transform,
                power_function=PowerFunction.CONSTANT,  # Assuming constant for now
                depth_start=float(stack_channel.get("start_depth", 0)),
                depth_end=float(stack_channel.get("end_depth", 0)),
                depth_step=float(stack_params.get("step_size", 1)),
                depth_unit=SizeUnit.UM,
            )
            images.append(image.model_dump())

        return channels, images

    def _create_slap_components(self, stream: Dict, light_sources: List, detectors: List) -> tuple:
        """Create channels and images for SLAP modality"""
        channels = []
        images = []

        for i, slap_fov in enumerate(stream.get("slap_fovs", [])):
            # Create channel for this SLAP FOV
            channel = {
                "object_type": "Channel config",
                "channel_name": f"SLAP_Channel_{i}",
                "detector": (
                    self._upgrade_detector_config(detectors[0])
                    if detectors
                    else {
                        "object_type": "Detector config",
                        "device_name": "Unknown Detector",
                        "exposure_time": 1.0,
                        "exposure_time_unit": "millisecond",
                        "trigger_type": "Internal",
                    }
                ),
                "light_sources": [],
            }
            channels.append(channel)

            # Create SLAP plane and image
            plane = self._upgrade_slap_fov_to_plane(slap_fov)
            image = {
                "object_type": "Planar image",
                "channel_name": f"SLAP_Channel_{i}",
                "planes": [plane],
                "image_to_acquisition_transform": {"type": "translation", "translation": [0, 0, 0]},
            }
            images.append(image)

        return channels, images

    def _create_fiber_components(self, stream: Dict, light_sources: List, detectors: List) -> tuple:
        """Create channels and images for fiber photometry modality"""
        channels = []
        images = []

        for fiber_conn in stream.get("fiber_connections", []):
            if "channel" in fiber_conn:
                channel_data = fiber_conn["channel"]
                channel = {
                    "object_type": "Channel config",
                    "channel_name": channel_data.get("channel_name", "Unknown Channel"),
                    "intended_measurement": channel_data.get("intended_measurement"),
                    "detector": {
                        "object_type": "Detector config",
                        "device_name": channel_data.get("detector_name", "Unknown Detector"),
                        "exposure_time": 1.0,
                        "exposure_time_unit": "millisecond",
                        "trigger_type": "Internal",
                    },
                    "light_sources": [],
                    "emission_wavelength": channel_data.get("emission_wavelength"),
                    "emission_wavelength_unit": "nanometer" if channel_data.get("emission_wavelength") else None,
                }
                channels.append(channel)

        return channels, images

    def _create_sampling_strategy(self, stream: Dict, modality: str) -> Optional[Dict]:
        """Create sampling strategy based on modality and stream data"""
        frame_rate = None

        if modality in ["ophys", "pophys"] and stream.get("ophys_fovs"):
            fov = stream["ophys_fovs"][0]
            frame_rate = fov.get("frame_rate")
        elif modality == "slap" and stream.get("slap_fovs"):
            slap_fov = stream["slap_fovs"][0]
            frame_rate = slap_fov.get("frame_rate")

        if frame_rate:
            return {"object_type": "Sampling strategy", "frame_rate": float(frame_rate), "frame_rate_unit": "hertz"}
        return None

    def _create_imaging_config(self, stream: Dict) -> Optional[Dict]:
        """Create ImagingConfig from stream data using modality-specific orchestration"""

        # Determine the primary imaging modality
        modality = self._determine_stream_modality(stream)
        if not modality:
            return None

        # Get light sources and detectors for reference
        light_sources = stream.get("light_sources", [])
        if not isinstance(light_sources, list):
            light_sources = [light_sources]
        detectors = stream.get("detectors", [])

        # Create components based on modality
        channels = []
        images = []

        if modality in ["ophys", "pophys"]:
            channels, images = self._create_ophys_components(stream, light_sources, detectors)
        elif modality == "slap":
            channels, images = self._create_slap_components(stream, light_sources, detectors)

        # Don't create config if no channels
        if not channels:
            return None

        # Create sampling strategy
        sampling_strategy = self._create_sampling_strategy(stream, modality)

        # Create the ImagingConfig
        return ImagingConfig(
            device_name="Imaging System",
            channels=channels,
            images=images,
            sampling_strategy=sampling_strategy,
        ).model_dump()

    def _upgrade_data_stream(self, stream: Dict, rig_id: str) -> Dict:
        """Upgrade a single data stream from v1 to v2"""
        # Extract modalities
        modalities = []
        for modality in stream.get("stream_modalities", []):
            if isinstance(modality, dict):
                abbreviation = modality.get("abbreviation", "")
                try:
                    modality_obj = Modality.from_abbreviation(abbreviation)
                    modalities.append(modality_obj.model_dump())
                except Exception:
                    # Default to behavior if unknown
                    modalities.append(Modality.BEHAVIOR.model_dump())
            else:
                modalities.append(Modality.BEHAVIOR.model_dump())

        # Collect active devices
        active_devices = []
        active_devices.extend(stream.get("daq_names", []))
        active_devices.extend(stream.get("camera_names", []))

        # Add device names from modules
        for ephys_module in stream.get("ephys_modules", []):
            active_devices.append(ephys_module.get("assembly_name", "Unknown Assembly"))
        for fiber_module in stream.get("fiber_modules", []):
            active_devices.append(fiber_module.get("assembly_name", "Unknown Fiber Assembly"))
        for stick_microscope in stream.get("stick_microscopes", []):
            active_devices.append(stick_microscope.get("assembly_name", "Unknown Stick Microscope"))

        # Create configurations and connections
        configurations, connections = self._upgrade_all_device_configurations(stream, rig_id)

        # Make sure all configuration devices are in active devices
        configuration_device_names = [config.get("device_name") for config in configurations]
        connection_device_names = [conn.get("source_device") for conn in connections] + [
            conn.get("target_device") for conn in connections
        ]
        active_devices = list(set(active_devices + configuration_device_names + connection_device_names))

        # Create the data stream
        return DataStream(
            stream_start_time=stream.get("stream_start_time"),
            stream_end_time=stream.get("stream_end_time"),
            modalities=modalities,
            active_devices=active_devices,
            configurations=configurations,
            connections=connections,
            notes=stream.get("notes"),
        ).model_dump()

    def _create_performance_metrics(self, epoch: Dict) -> Optional[Dict]:
        """Create performance metrics from epoch data"""
        performance_metrics = None

        # Create performance metrics
        reward_consumed_during_epoch = epoch.get("reward_consumed_during_epoch")
        reward_consumed_unit = epoch.get("reward_consumed_unit")

        # Try to generate unit if missing
        if reward_consumed_during_epoch and not reward_consumed_unit:
            if float(reward_consumed_during_epoch) < 3:
                reward_consumed_unit = VolumeUnit.ML
            else:
                reward_consumed_unit = VolumeUnit.UL

        if any(
            [
                epoch.get("trials_total"),
                epoch.get("trials_finished"),
                epoch.get("trials_rewarded"),
                epoch.get("reward_consumed_during_epoch"),
            ]
        ):
            performance_metrics = PerformanceMetrics(
                trials_total=epoch.get("trials_total"),
                trials_finished=epoch.get("trials_finished"),
                trials_rewarded=epoch.get("trials_rewarded"),
                reward_consumed_during_epoch=reward_consumed_during_epoch,
                reward_consumed_unit=reward_consumed_unit,
                output_parameters=GenericModel(**epoch.get("output_parameters", {})),
            )

        return performance_metrics.model_dump() if performance_metrics else None

    def _get_software(self, epoch: Dict) -> Optional[Dict]:
        """Extract software information from epoch data, handling cases with multiple software entries"""
        software = epoch["software"]

        if isinstance(software, list):
            if len(software) == 1:
                software = software[0]
            elif len(software) == 2:
                names = [sw.get("name", "").lower() for sw in software]
                if "python" in names:
                    # If one is Python, take the other one
                    software = next((sw for sw in software if sw.get("name", "").lower() != "python"), None)
            else:
                # If there's two softwares, take the one that isn't Python
                print(software)
                raise ValueError("More than two software entries found, cannot upgrade")

        return software

    def _create_code_object(self, epoch: Dict) -> Optional[Dict]:
        """Create code object from epoch script"""
        code = None
        if epoch.get("script"):
            script_data = epoch["script"]

            stimulus_parameters = epoch.get("stimulus_parameters", [])
            if isinstance(stimulus_parameters, list):
                if len(stimulus_parameters) == 1:
                    stimulus_parameters = stimulus_parameters[0]
                elif len(stimulus_parameters) > 1:
                    split_parameters = {}
                    for i, params in enumerate(stimulus_parameters):
                        if "stimulus_name" in params:
                            split_parameters[params["stimulus_name"]] = params
                        else:
                            split_parameters[f"Stimulus_{i}"] = params
                    stimulus_parameters = split_parameters

            if not stimulus_parameters:
                stimulus_parameters = None

            if "parameters" in script_data:
                stimulus_parameters = (stimulus_parameters if stimulus_parameters else {}) | script_data["parameters"]

            software = self._get_software(epoch)

            if software:
                core_dependency = Software(
                    name=software.get("name", "unknown"),
                    version=software.get("version", None),
                )
            else:
                core_dependency = None

            code = Code(
                name=script_data.get("name", "Unknown Script"),
                version=script_data.get("version", "unknown"),
                url=script_data.get("url", "unknown") or "",
                parameters=stimulus_parameters,
                core_dependency=core_dependency,
            )
        return code.model_dump() if code else None

    def _determine_stimulus_modalities(self, epoch: dict) -> list:
        """Determine stimulus modalities from epoch data"""
        stimulus_modalities = epoch.get("stimulus_modalities", [])
        if not stimulus_modalities or stimulus_modalities == ["None"] or stimulus_modalities == [None]:
            stimulus_name = epoch.get("stimulus_name", "").lower()
            if "spontaneous" in stimulus_name:
                stimulus_modalities = [StimulusModality.NO_STIMULUS]
            if "the random reward stimulus" in stimulus_name:
                # This is the dynamic foraging task
                stimulus_modalities = [StimulusModality.AUDITORY]
        return stimulus_modalities

    def _create_speaker_config(self, epoch: dict) -> Optional[dict]:
        """Create speaker configuration if present"""
        if not epoch.get("speaker_config"):
            return None

        speaker_data = epoch["speaker_config"]
        return SpeakerConfig(
            device_name=speaker_data.get("name", "Unknown Speaker"),
            volume=float(speaker_data.get("volume", 0)) if speaker_data.get("volume") else None,
            volume_unit=SoundIntensityUnit.DB,
        ).model_dump()

    def _create_light_source_configs(self, epoch: dict) -> list:
        """Create light source configurations if present"""
        configs = []
        if epoch.get("light_source_config"):
            light_source_configs = epoch.get("light_source_config", [])
            if not isinstance(light_source_configs, list):
                light_source_configs = [light_source_configs]
            for light_source in light_source_configs:
                config = self._upgrade_light_source_config(light_source)
                if config:
                    configs.append(config)
        return configs

    def _determine_stimulus_name(self, epoch: dict) -> str:
        """Determine stimulus name from epoch data"""
        stimulus_name = epoch.get("stimulus_name")
        if not stimulus_name:
            # Try to get from inside the stimulus itself
            stimulus_name = epoch.get("stimulus", {}).get("stimulus_name", "Unknown Stimulus")
        return stimulus_name

    def _handle_legacy_stimulus_data(self, epoch: dict, code: Optional[dict]) -> Optional[dict]:
        """Handle legacy stimulus data and merge with code object"""
        if "stimulus" in epoch and epoch["stimulus"]:
            stimulus_data = epoch["stimulus"]
            if not code:
                # Create a basic code object from this
                code = Code(
                    name="Code",
                    version="unknown",
                    url="unknown",
                    parameters=stimulus_data,
                ).model_dump()
            else:
                # Merge parameters if possible
                if stimulus_data.get("parameters"):
                    if code.get("parameters"):
                        code["parameters"] = code["parameters"] | stimulus_data["parameters"]
                    else:
                        code["parameters"] = stimulus_data["parameters"]
        return code

    def _upgrade_stimulus_epoch(self, epoch: dict) -> dict:
        """Upgrade stimulus epoch from v1 to v2"""
        # Determine stimulus modalities
        stimulus_modalities = self._determine_stimulus_modalities(epoch)

        # Create performance metrics
        performance_metrics = self._create_performance_metrics(epoch)

        # Create configurations
        configurations = []

        # Add speaker config if present
        speaker_config = self._create_speaker_config(epoch)
        if speaker_config:
            configurations.append(speaker_config)

        # Add light source configs if present
        light_configs = self._create_light_source_configs(epoch)
        configurations.extend(light_configs)

        # Create code object if script is present
        code = self._create_code_object(epoch)

        # Determine stimulus name
        stimulus_name = self._determine_stimulus_name(epoch)

        # Handle legacy stimulus data
        code = self._handle_legacy_stimulus_data(epoch, code)

        return StimulusEpoch(
            stimulus_start_time=epoch.get("stimulus_start_time"),
            stimulus_end_time=epoch.get("stimulus_end_time"),
            stimulus_name=stimulus_name,
            stimulus_modalities=stimulus_modalities,
            performance_metrics=performance_metrics,
            code=code,
            active_devices=epoch.get("stimulus_device_names", []),
            configurations=configurations,
            notes=epoch.get("notes"),
        ).model_dump()

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the session data to v2.0 acquisition"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Handle nested session data structure
        session_data = data.get("session", data)

        # Extract V1 fields
        protocol_id = session_data.get("protocol_id", [])
        if not isinstance(protocol_id, list):
            protocol_id = [protocol_id]
        experimenter_full_name = session_data.get("experimenter_full_name", [])
        subject_id = session_data.get("subject_id")
        rig_id = session_data.get("rig_id")
        calibrations = session_data.get("calibrations", [])
        maintenance = session_data.get("maintenance", [])
        session_start_time = session_data.get("session_start_time")
        session_end_time = session_data.get("session_end_time")
        data_streams = session_data.get("data_streams", [])
        stimulus_epochs = session_data.get("stimulus_epochs", [])
        notes = session_data.get("notes")

        # Session-specific fields
        animal_weight_prior = session_data.get("animal_weight_prior")
        animal_weight_post = session_data.get("animal_weight_post")
        weight_unit = session_data.get("weight_unit", "gram")
        anaesthesia = session_data.get("anaesthesia")
        mouse_platform_name = session_data.get("mouse_platform_name", "Unknown Platform")
        reward_consumed_total = session_data.get("reward_consumed_total")
        reward_consumed_unit = session_data.get("reward_consumed_unit", "milliliter")

        # Upgrade experimenter names to Person objects
        experimenters = self._upgrade_experimenter_names(experimenter_full_name)

        # Upgrade data streams
        upgraded_data_streams = []
        for stream in data_streams:
            upgraded_stream = self._upgrade_data_stream(stream, rig_id)
            upgraded_data_streams.append(upgraded_stream)

        # Upgrade stimulus epochs
        upgraded_stimulus_epochs = []
        for epoch in stimulus_epochs:
            upgraded_epoch = self._upgrade_stimulus_epoch(epoch)
            upgraded_stimulus_epochs.append(upgraded_epoch)

        # Upgrade calibrations and maintenance
        upgraded_calibrations = [upgrade_calibration(cal) for cal in calibrations]
        upgraded_maintenance = self._upgrade_maintenance(maintenance)

        # Determine acquisition type
        acquisition_type = self._determine_acquisition_type(session_data)

        # Create subject details
        subject_details = AcquisitionSubjectDetails(
            animal_weight_prior=animal_weight_prior,
            animal_weight_post=animal_weight_post,
            weight_unit=MassUnit.G if weight_unit == "gram" else MassUnit.KG,
            anaesthesia=anaesthesia,
            mouse_platform_name=mouse_platform_name,
            reward_consumed_total=reward_consumed_total,
            reward_consumed_unit=VolumeUnit.ML if reward_consumed_unit == "milliliter" else VolumeUnit.UL,
        ).model_dump()

        # Validate and adjust session start/end times
        session_start_time, session_end_time, notes = self._validate_and_adjust_session_times(
            session_start_time, session_end_time, upgraded_data_streams, upgraded_stimulus_epochs, notes
        )

        # Get the iacuc_protocl
        ethics_review_id = session_data.get("iacuc_protocol")
        if not isinstance(ethics_review_id, list):
            ethics_review_id = [ethics_review_id] if ethics_review_id else []

        # Build V2 acquisition object
        acquisition = Acquisition(
            schema_version=schema_version,
            subject_id=subject_id,
            acquisition_start_time=session_start_time,
            acquisition_end_time=session_end_time,
            experimenters=experimenters,
            protocol_id=protocol_id if protocol_id else None,
            instrument_id=rig_id,
            acquisition_type=acquisition_type,
            notes=notes,
            calibrations=upgraded_calibrations,
            maintenance=upgraded_maintenance,
            data_streams=upgraded_data_streams,
            stimulus_epochs=upgraded_stimulus_epochs,
            subject_details=subject_details,
            ethics_review_id=ethics_review_id,
        )

        return acquisition.model_dump()

    def _upgrade_all_device_configurations(self, stream: Dict, rig_id: str) -> tuple:
        """Upgrade all device configurations from a stream and return configurations and connections"""
        configurations = []
        connections = []

        # Light source and detector configs
        for light_source in stream.get("light_sources", []):
            config = self._upgrade_light_source_config(light_source)
            if config:
                configurations.append(config)

        for detector in stream.get("detectors", []):
            configurations.append(self._upgrade_detector_config(detector))

        # Ephys configs
        for ephys_module in stream.get("ephys_modules", []):
            configs = self._upgrade_ephys_module_to_configs(ephys_module)
            configurations.extend(configs)

        # Fiber upgrader
        patchcord_configs, fiber_connections = self._upgrade_fiber(stream)
        configurations.extend(patchcord_configs)
        connections.extend(fiber_connections)

        # MRI configs
        for mri_scan in stream.get("mri_scans", []):
            configurations.append(self._upgrade_mri_scan_to_config(mri_scan))

        # Imaging config
        imaging_config = self._create_imaging_config(stream)
        if imaging_config:
            configurations.append(imaging_config)

        return configurations, connections

    def _validate_and_adjust_session_times(
        self, session_start_time, session_end_time, upgraded_data_streams, upgraded_stimulus_epochs, notes
    ):
        """Validate session times against data streams and epochs, adjusting if necessary"""
        # Validate that the start/end times are before all the data streams and epochs
        start_times = []
        end_times = []
        for stream in upgraded_data_streams:
            start_times.append(stream.get("stream_start_time"))
            end_times.append(stream.get("stream_end_time"))
        for epoch in upgraded_stimulus_epochs:
            start_times.append(epoch.get("stimulus_start_time"))
            end_times.append(epoch.get("stimulus_end_time"))

        # Pacific timezone - automatically handles PST/PDT transitions
        pacific_tz = ZoneInfo("America/Los_Angeles")

        # Helper function to ensure datetime has Pacific timezone
        def ensure_pacific_timezone(dt):
            """Convert a datetime to Pacific timezone if not already set."""
            if dt is None:
                return None
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pacific_tz)
            return dt

        # Convert start and end times to datetime objects and ensure Pacific timezone
        session_start_time = ensure_pacific_timezone(session_start_time)
        session_end_time = ensure_pacific_timezone(session_end_time)

        # Invert start/end time if they are in the wrong order
        if session_start_time and session_end_time and session_start_time > session_end_time:
            session_start_time, session_end_time = session_end_time, session_start_time

        # Convert all times in lists to datetime objects with Pacific timezone, filter out None values
        valid_start_times = [ensure_pacific_timezone(t) for t in start_times if t is not None]
        valid_start_times = [t for t in valid_start_times if t is not None]
        valid_end_times = [ensure_pacific_timezone(t) for t in end_times if t is not None]
        valid_end_times = [t for t in valid_end_times if t is not None]

        if valid_start_times and session_start_time and any(start >= session_start_time for start in valid_start_times):
            min_start = min(valid_start_times)
            notes = (notes if notes else "") + (
                f" (v1v2 upgrade) Session start time was adjusted from {session_start_time} " f"to {min_start}"
            )
            session_start_time = min_start
        if valid_end_times and session_end_time and any(end <= session_end_time for end in valid_end_times):
            max_end = max(valid_end_times)
            notes = (notes if notes else "") + (
                f" (v1v2 upgrade) Session end time was adjusted from {session_end_time} " f"to {max_end}"
            )
            session_end_time = max_end

        return session_start_time, session_end_time, notes
