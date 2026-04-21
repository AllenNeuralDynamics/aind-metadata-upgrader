"""<=v1.4 to v2.0 acquisition upgrade functions"""

from typing import Dict, List, Optional

from aind_data_schema.core.acquisition import AcquisitionSubjectDetails

from aind_metadata_upgrader.acquisition.v1v2_tiles import (
    upgrade_tiles_to_data_stream,
)
from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_calibration, upgrade_reagent, ensure_pacific_timezone
from aind_data_schema.components.coordinates import (
    CoordinateSystem,
    Origin,
    Axis,
    AxisName,
    Direction,
)


class AcquisitionV1V2(CoreUpgrader):
    """Upgrade acquisition from v1.4 to v2.0"""

    def _upgrade_experimenter_names(self, experimenter_names: List[str]) -> List[Dict]:
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
                    if "reagents" in maint and maint["reagents"]:
                        maint["reagents"] = [upgrade_reagent(reagent) for reagent in maint["reagents"]]
                    upgraded_maintenance.append(maint)
        return upgraded_maintenance

    def _create_coordinate_system_from_axes(self, axes: List[Dict]) -> Optional[Dict]:
        """Create coordinate system from V1 axes information"""
        if not axes:
            return None

        # Sort axes by dimension to ensure consistent ordering
        sorted_axes = sorted(axes, key=lambda x: x["dimension"])

        # Map V1 direction strings to V2 Direction enums and coordinate system letters
        direction_mapping = {
            "Left_to_right": (Direction.LR, "R"),
            "Right_to_left": (Direction.RL, "L"),
            "Anterior_to_posterior": (Direction.AP, "P"),
            "Posterior_to_anterior": (Direction.PA, "A"),
            "Superior_to_inferior": (Direction.SI, "I"),
            "Inferior_to_superior": (Direction.IS, "S"),
        }

        # Extract direction enums and letters for each dimension (0, 1, 2)
        try:
            dim0_direction, dim0_letter = direction_mapping[sorted_axes[0]["direction"]]
            dim1_direction, dim1_letter = direction_mapping[sorted_axes[1]["direction"]]
            dim2_direction, dim2_letter = direction_mapping[sorted_axes[2]["direction"]]
        except (KeyError, IndexError) as e:
            print(f"Invalid axes configuration: {axes}")
            raise ValueError(f"Invalid or incomplete axes configuration: {e}")

        coordinate_system_name = f"SPIM_{dim0_letter}{dim1_letter}{dim2_letter}"

        # Build axes preserving the original V1 axis names (X/Y/Z) with
        # their recorded directions, ordered by dimension.
        axis_name_map = {"X": AxisName.X, "Y": AxisName.Y, "Z": AxisName.Z}
        axes_list = []
        for ax in sorted_axes:
            ax_name = axis_name_map.get(ax["name"], AxisName.X)
            ax_direction = direction_mapping[ax["direction"]][0]
            axes_list.append(Axis(name=ax_name, direction=ax_direction))

        # Create the coordinate system
        coordinate_system = CoordinateSystem(
            name=coordinate_system_name,
            origin=Origin.ORIGIN,
            axis_unit=sorted_axes[0]["unit"],
            axes=axes_list,
        )
        return coordinate_system.model_dump()

    def _determine_acquisition_type(self, data: Dict) -> str:
        """Determine acquisition type from V1 data"""
        # Try to infer from session_type or other fields
        session_type = data.get("session_type")
        if session_type:
            return session_type

        # Check if we have tiles (imaging) or other indicators
        if data.get("tiles"):
            return "Imaging session"

        # Default fallback
        return "Acquisition session"

    def _process_session_times(self, session_start_time, session_end_time):
        """Process and validate session start and end times with Pacific timezone"""

        # Convert start and end times to datetime objects and ensure Pacific timezone
        session_start_time = ensure_pacific_timezone(session_start_time)
        session_end_time = ensure_pacific_timezone(session_end_time)

        # Invert start/end time if they are in the wrong order
        if session_start_time and session_end_time and session_start_time > session_end_time:
            session_start_time, session_end_time = session_end_time, session_start_time

        return session_start_time, session_end_time

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict]) -> dict:
        """Upgrade the acquisition data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Fields that are removed in V2 (just for documentation):
        # - local_storage_directory, external_storage_directory

        # Extract V1 fields
        protocol_id = data.get("protocol_id", [])
        experimenter_full_name = data.get("experimenter_full_name", [])
        specimen_id = data.get("specimen_id")
        subject_id = data.get("subject_id")
        instrument_id = data.get("instrument_id")
        calibrations = data.get("calibrations", [])
        if not calibrations:
            calibrations = []
        maintenance = data.get("maintenance", [])
        session_start_time = data.get("session_start_time")
        session_end_time = data.get("session_end_time")
        tiles = data.get("tiles", [])
        axes = data.get("axes", [])
        notes = data.get("notes")

        # Convert start and end times to Pacific timezone
        session_start_time, session_end_time = self._process_session_times(session_start_time, session_end_time)

        # Repair specimen_id, if needed
        if not specimen_id:
            specimen_id = f"{subject_id}_001"

        active_objectives = data.get("active_objectives", [])

        software = data.get("software", [])

        chamber_immersion = data.get("chamber_immersion")
        sample_immersion = data.get("sample_immersion")

        # Upgrade experimenter names to Person objects
        experimenters = self._upgrade_experimenter_names(experimenter_full_name)

        # Create coordinate system from axes (needed both at the acquisition
        # level and inside ImagingConfig when ImageSPIM tiles are present)
        coordinate_system = self._create_coordinate_system_from_axes(axes)

        # Upgrade tiles to data streams
        if session_start_time and session_end_time:

            start_str = (
                session_start_time.isoformat() if hasattr(session_start_time, "isoformat") else str(session_start_time)
            )
            end_str = session_end_time.isoformat() if hasattr(session_end_time, "isoformat") else str(session_end_time)

            # Get fluorescence filters and light sources from instrument if available.
            # When instrument metadata is absent or null, fall back to empty lists —
            # tile channel data will be used directly to build LaserConfig/DetectorConfig.
            if metadata and metadata.get("instrument"):
                fluorescence_filters = metadata["instrument"].get("fluorescence_filters", [])
                light_sources = metadata["instrument"].get("light_sources", [])
            else:
                fluorescence_filters = []
                light_sources = []

            data_streams = upgrade_tiles_to_data_stream(
                tiles,
                start_str,
                end_str,
                chamber_immersion=chamber_immersion or {},
                sample_immersion=sample_immersion,
                device_name=instrument_id or "",
                software=software,
                fluorescence_filters=fluorescence_filters,
                light_sources=light_sources,
                coordinate_system=coordinate_system,
            )
            if active_objectives:
                data_streams[0]["active_devices"].extend(active_objectives)
        else:
            # If no session times, create empty data streams
            raise NotImplementedError()

        # Upgrade calibrations and maintenance
        upgraded_calibrations = [upgrade_calibration(cal) for cal in calibrations]
        upgraded_maintenance = self._upgrade_maintenance(maintenance)

        # Determine acquisition type
        acquisition_type = self._determine_acquisition_type(data)

        raw_subject_details = data.get("subject_details")
        if raw_subject_details:
            subject_details = raw_subject_details
        else:
            subject_details = AcquisitionSubjectDetails(
                mouse_platform_name="unknown",
            ).model_dump()

        # Build V2 acquisition object
        output = {
            "schema_version": schema_version,
            "subject_id": subject_id,
            "specimen_id": specimen_id,
            "acquisition_start_time": session_start_time,
            "acquisition_end_time": session_end_time,
            "experimenters": experimenters,
            "protocol_id": protocol_id if protocol_id else None,
            "ethics_review_id": None,
            "instrument_id": instrument_id,
            "acquisition_type": acquisition_type,
            "notes": notes,
            "coordinate_system": coordinate_system,
            "calibrations": upgraded_calibrations,
            "maintenance": upgraded_maintenance,
            "data_streams": data_streams,
            "stimulus_epochs": [],  # No stimulus epochs for acquisition -> acquisition
            "subject_details": subject_details,
        }

        return output
