"""<=v1.4 to v2.0 session upgrade functions"""

from typing import Dict, List, Optional, Union
from aind_data_schema.components.identifiers import Person, Code
from aind_data_schema.core.acquisition import (
    AcquisitionSubjectDetails,
    DataStream,
    StimulusEpoch,
    PerformanceMetrics,
    Acquisition
)
from aind_data_schema.components.configs import (
    DetectorConfig,
    LaserConfig,
    LightEmittingDiodeConfig,
    ManipulatorConfig,
    EphysAssemblyConfig,
    FiberAssemblyConfig,
    PatchCordConfig,
    ImagingConfig,
    Channel,
    Plane,
    CoupledPlane,
    SlapPlane,
    SampleChamberConfig,
    Immersion,
    MRIScan,
    SpeakerConfig,
    TriggerType,
    MriScanSequence,
    ScanType,
    SubjectPosition,
    SlapAcquisitionType
)
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.stimulus_modality import StimulusModality
from aind_data_schema_models.devices import ImmersionMedium
from aind_data_schema_models.units import (
    TimeUnit, PowerUnit, SizeUnit,
    MassUnit, VolumeUnit, SoundIntensityUnit
)
from aind_data_schema.base import GenericModel
from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_calibration


class SessionV1V2(CoreUpgrader):
    """Upgrade session from v1.4 to v2.0 (acquisition)"""

    def _upgrade_experimenter_names_to_persons(self, experimenter_names: List[str]) -> List[Dict]:
        """Convert experimenter full names to Person objects"""
        experimenters = []
        for name in experimenter_names:
            if name and name.strip():
                experimenters.append(Person(name=name.strip()).model_dump())
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

    def _upgrade_light_source_config(self, light_source: Dict) -> Union[Dict, None]:
        """Upgrade light source config from v1 to v2"""
        if not light_source:
            return None

        device_type = light_source.get("device_type")
        device_name = light_source.get("name", "Unknown Device")
        excitation_power = light_source.get("excitation_power")
        power_unit = light_source.get("excitation_power_unit")

        if device_type == "Laser":
            return LaserConfig(
                device_name=device_name,
                wavelength=light_source.get("wavelength", 0),
                wavelength_unit=SizeUnit.NM,
                power=float(excitation_power) if excitation_power else None,
                power_unit=PowerUnit.MW if power_unit == "milliwatt" else PowerUnit.PERCENT
            ).model_dump()
        elif device_type == "Light emitting diode":
            return LightEmittingDiodeConfig(
                device_name=device_name,
                power=float(excitation_power) if excitation_power else None,
                power_unit=PowerUnit.MW if power_unit == "milliwatt" else PowerUnit.PERCENT
            ).model_dump()
        return None

    def _upgrade_detector_config(self, detector: Dict) -> Dict:
        """Upgrade detector config from v1 to v2"""
        return DetectorConfig(
            device_name=detector.get("name", "Unknown Detector"),
            exposure_time=float(detector.get("exposure_time", 1.0)),
            exposure_time_unit=TimeUnit.MS,
            trigger_type=TriggerType.INTERNAL if detector.get("trigger_type") == "Internal" else TriggerType.EXTERNAL
        ).model_dump()

    def _upgrade_ephys_module_to_configs(self, ephys_module: Dict) -> List[Dict]:
        """Convert ephys module to EphysAssemblyConfig and ManipulatorConfig"""
        configs = []

        # Create ManipulatorConfig for the manipulator/dome module
        manipulator_config = ManipulatorConfig(
            device_name=ephys_module.get("assembly_name", "Unknown Assembly")
        ).model_dump()
        configs.append(manipulator_config)

        # Create EphysAssemblyConfig
        ephys_config = EphysAssemblyConfig(
            device_name=ephys_module.get("assembly_name", "Unknown Assembly")
        ).model_dump()
        configs.append(ephys_config)

        return configs

    def _upgrade_fiber_connection_to_config(self, fiber_conn: Dict) -> Dict:
        """Convert fiber connection to PatchCordConfig"""
        channels = []
        if "channel" in fiber_conn:
            channel_data = fiber_conn["channel"]
            channel = Channel(
                channel_name=channel_data.get("channel_name", "Ch1")
            ).model_dump()
            channels.append(channel)

        return PatchCordConfig(
            device_name=fiber_conn.get("patch_cord_name", "Unknown Patch Cord"),
            channels=channels
        ).model_dump()

    def _upgrade_fiber_module_to_config(self, fiber_module: Dict) -> Dict:
        """Convert fiber module to FiberAssemblyConfig"""
        return FiberAssemblyConfig(
            device_name=fiber_module.get("assembly_name", "Unknown Fiber Assembly")
        ).model_dump()

    def _upgrade_ophys_fov_to_plane(self, fov: Dict) -> Dict:
        """Convert ophys FOV to Plane"""
        # Determine the targeted structure
        targeted_structure = fov.get("targeted_structure")
        if isinstance(targeted_structure, dict):
            # It's already a CCFv3 object
            ccf_structure = targeted_structure
        else:
            # It's a string, try to convert
            ccf_structure = {"name": str(targeted_structure), "acronym": "Unknown", "id": "0"}

        plane = Plane(
            depth=float(fov.get("imaging_depth", 0)),
            depth_unit=SizeUnit.UM,
            power=float(fov.get("power", 0)) if fov.get("power") else 0.0,
            power_unit=PowerUnit.PERCENT,
            targeted_structure=ccf_structure
        ).model_dump()

        # Handle coupled FOVs
        if fov.get("coupled_fov_index") is not None:
            coupled_plane = CoupledPlane(
                depth=float(fov.get("imaging_depth", 0)),
                depth_unit=SizeUnit.UM,
                power=float(fov.get("power", 0)) if fov.get("power") else 0.0,
                power_unit=PowerUnit.PERCENT,
                targeted_structure=ccf_structure,
                plane_index=fov.get("index", 0),
                coupled_plane_index=fov.get("coupled_fov_index"),
                power_ratio=float(fov.get("power_ratio", 1.0)) if fov.get("power_ratio") else 1.0
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
        acquisition_type = (SlapAcquisitionType.PARENT if session_type == "Parent"
                            else SlapAcquisitionType.BRANCH)

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
            path_to_array_of_frame_rates=slap_fov.get("path_to_array_of_frame_rates", "")
        ).model_dump()

    def _upgrade_mri_scan_to_config(self, scan: Dict) -> Dict:
        """Convert MRI scan to MRIScan config"""
        return MRIScan(
            device_name=scan.get("mri_scanner", {}).get("name", "Unknown Scanner"),
            scan_sequence_type=(MriScanSequence.RARE
                               if scan.get("scan_sequence_type") == "RARE"
                               else MriScanSequence.OTHER),
            scan_type=(ScanType.SCAN_3D 
                      if scan.get("scan_type") == "3D Scan" 
                      else ScanType.SETUP),
            subject_position=(SubjectPosition.PRONE 
                             if scan.get("subject_position") == "Prone" 
                             else SubjectPosition.SUPINE)
        ).model_dump()

    def _create_imaging_config(self, stream: Dict) -> Optional[Dict]:
        """Create ImagingConfig from stream data"""
        channels = []

        # Create channels from detectors and light sources
        detectors = stream.get("detectors", [])
        light_sources = stream.get("light_sources", [])

        if detectors and light_sources:
            # Create a channel combining detector and light source info
            detector = detectors[0]  # Use first detector
            light_source = light_sources[0]  # Use first light source

            detector_config = self._upgrade_detector_config(detector)
            light_configs = []
            light_config = self._upgrade_light_source_config(light_source)
            if light_config:
                light_configs.append(light_config)

            channel = Channel(
                channel_name="Ch1",
                detector=detector_config,
                light_sources=light_configs
            ).model_dump()
            channels.append(channel)

        if channels:
            return ImagingConfig(
                device_name="Imaging System",
                channels=channels
            ).model_dump()
        return None

    def _create_sample_chamber_config(self, device_name: str) -> Dict:
        """Create a basic SampleChamberConfig"""
        # Create basic immersion - will be overridden if chamber_immersion exists
        basic_immersion = Immersion(
            medium=ImmersionMedium.AIR,
            refractive_index=1.0
        ).model_dump()

        return SampleChamberConfig(
            device_name=device_name,
            chamber_immersion=basic_immersion
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
                except:
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

        # Create configurations
        configurations = []

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

        # Fiber configs
        for fiber_conn in stream.get("fiber_connections", []):
            configurations.append(self._upgrade_fiber_connection_to_config(fiber_conn))

        for fiber_module in stream.get("fiber_modules", []):
            configurations.append(self._upgrade_fiber_module_to_config(fiber_module))

        # MRI configs
        for mri_scan in stream.get("mri_scans", []):
            configurations.append(self._upgrade_mri_scan_to_config(mri_scan))

        # Imaging config
        imaging_config = self._create_imaging_config(stream)
        if imaging_config:
            configurations.append(imaging_config)

        # Sample chamber config (basic one for now)
        if stream.get("ophys_fovs") or stream.get("slap_fovs"):
            configurations.append(self._create_sample_chamber_config(rig_id))

        # Create the data stream
        return DataStream(
            stream_start_time=stream.get("stream_start_time"),
            stream_end_time=stream.get("stream_end_time"),
            modalities=modalities,
            active_devices=active_devices,
            configurations=configurations,
            notes=stream.get("notes")
        ).model_dump()

    def _upgrade_stimulus_epoch(self, epoch: Dict) -> Dict:
        """Upgrade stimulus epoch from v1 to v2"""
        # Convert stimulus modalities
        stimulus_modalities = []
        for modality in epoch.get("stimulus_modalities", []):
            if modality == "Visual":
                stimulus_modalities.append(StimulusModality.VISUAL)
            elif modality == "Auditory":
                stimulus_modalities.append(StimulusModality.AUDITORY)
            elif modality == "Olfactory":
                stimulus_modalities.append(StimulusModality.OLFACTORY)
            elif modality == "Optogenetics":
                stimulus_modalities.append(StimulusModality.OPTOGENETICS)
            elif modality == "Free moving":
                stimulus_modalities.append(StimulusModality.FREE_MOVING)
            elif modality == "Virtual reality":
                stimulus_modalities.append(StimulusModality.VIRTUAL_REALITY)
            elif modality == "Wheel friction":
                stimulus_modalities.append(StimulusModality.WHEEL_FRICTION)
            else:
                stimulus_modalities.append(StimulusModality.NONE)

        # Create performance metrics
        performance_metrics = None
        if any([
            epoch.get("trials_total"),
            epoch.get("trials_finished"),
            epoch.get("trials_rewarded"),
            epoch.get("reward_consumed_during_epoch")
        ]):
            performance_metrics = PerformanceMetrics(
                trials_total=epoch.get("trials_total"),
                trials_finished=epoch.get("trials_finished"),
                trials_rewarded=epoch.get("trials_rewarded"),
                reward_consumed_during_epoch=epoch.get("reward_consumed_during_epoch"),
                reward_consumed_unit=VolumeUnit.UL,
                output_parameters=GenericModel(**epoch.get("output_parameters", {}))
            ).model_dump()

        # Create configurations
        configurations = []

        # Speaker config
        if epoch.get("speaker_config"):
            speaker_data = epoch["speaker_config"]
            speaker_config = SpeakerConfig(
                device_name=speaker_data.get("name", "Unknown Speaker"),
                volume=float(speaker_data.get("volume", 0)) if speaker_data.get("volume") else None,
                volume_unit=SoundIntensityUnit.DB
            ).model_dump()
            configurations.append(speaker_config)

        # Light source configs for stimulation
        for light_source in epoch.get("light_source_config", []):
            config = self._upgrade_light_source_config(light_source)
            if config:
                configurations.append(config)

        # Create code object if script is present
        code = None
        if epoch.get("script"):
            script_data = epoch["script"]
            code = Code(
                name=script_data.get("name", "Unknown Script"),
                version=script_data.get("version", "unknown"),
                url=script_data.get("url")
            ).model_dump()

        return StimulusEpoch(
            stimulus_start_time=epoch.get("stimulus_start_time"),
            stimulus_end_time=epoch.get("stimulus_end_time"),
            stimulus_name=epoch.get("stimulus_name", "Unknown Stimulus"),
            stimulus_modalities=stimulus_modalities,
            performance_metrics=performance_metrics,
            code=code,
            active_devices=epoch.get("stimulus_device_names", []),
            configurations=configurations,
            notes=epoch.get("notes")
        ).model_dump()

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the session data to v2.0 acquisition"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Handle nested session data structure
        session_data = data.get("session", data)

        # Extract V1 fields
        protocol_id = session_data.get("protocol_id", [])
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
        experimenters = self._upgrade_experimenter_names_to_persons(experimenter_full_name)

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
            reward_consumed_unit=VolumeUnit.ML if reward_consumed_unit == "milliliter" else VolumeUnit.UL
        ).model_dump()

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
            subject_details=subject_details
        )

        return acquisition.model_dump()
