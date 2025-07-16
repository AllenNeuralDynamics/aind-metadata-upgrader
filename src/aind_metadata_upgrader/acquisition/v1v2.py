"""<=v1.4 to v2.0 acquisition upgrade functions"""

from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from aind_data_schema.core.acquisition import AcquisitionSubjectDetails

from aind_metadata_upgrader.acquisition.v1v2_tiles import (
    upgrade_tiles_to_data_stream,
)
from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_calibration, upgrade_reagent
from aind_data_schema.components.coordinates import (
    CoordinateSystem,
    Origin,
    Axis,
    AxisName,
    Direction,
    CoordinateSystemLibrary,
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

        # Extract directions for each dimension (0, 1, 2)
        directions = [axis["direction"] for axis in sorted_axes]

        # Check for SPIM_RAI configuration - variant 1 (X=LR, Y=AP, Z=SI)
        if (
            directions[0] == "Superior_to_inferior"
            and directions[1] == "Anterior_to_posterior"
            and directions[2] == "Left_to_right"
        ):
            coordinate_system = CoordinateSystem(
                name="SPIM_RAI",
                origin=Origin.ORIGIN,
                axis_unit=axes[0]["unit"],
                axes=[
                    Axis(name=AxisName.X, direction=Direction.LR),
                    Axis(name=AxisName.Y, direction=Direction.AP),
                    Axis(name=AxisName.Z, direction=Direction.SI),
                ],
            )
            return coordinate_system.model_dump()

        # Check for SPIM_RAI configuration - variant 2 (X=LR, Y=PA, Z=SI)
        elif (
            directions[0] == "Superior_to_inferior"
            and directions[1] == "Posterior_to_anterior"
            and directions[2] == "Left_to_right"
        ):
            coordinate_system = CoordinateSystem(
                name="SPIM_RAI",
                origin=Origin.ORIGIN,
                axis_unit=axes[0]["unit"],
                axes=[
                    Axis(name=AxisName.X, direction=Direction.LR),
                    Axis(name=AxisName.Y, direction=Direction.AP),
                    Axis(name=AxisName.Z, direction=Direction.SI),
                ],
            )
            return coordinate_system.model_dump()

        # Check for SPIM_RPI configuration (X=RL, Y=PA, Z=IS)
        elif (
            directions[0] == "Inferior_to_superior"
            and directions[1] == "Anterior_to_posterior"
            and directions[2] == "Left_to_right"
        ):
            return CoordinateSystemLibrary.SPIM_RPI.model_dump()

        # Check for SPIM_LPS configuration (X=PA, Y=IS, Z=RL)
        elif (
            directions[0] == "Right_to_left"
            and directions[1] == "Inferior_to_superior"
            and directions[2] == "Posterior_to_anterior"
        ):
            return CoordinateSystemLibrary.SPIM_LPS.model_dump()

        else:
            print(axes)
            raise ValueError("Unsupported axes configuration for coordinate system creation, needs to be implemented")

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
        # Pacific timezone - automatically handles PST/PDT transitions
        pacific_tz = ZoneInfo("America/Los_Angeles")

        # Helper function to ensure datetime has Pacific timezone
        def ensure_pacific_timezone(dt):
            """Ensure datetime is in Pacific timezone"""
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

        return session_start_time, session_end_time

    def upgrade(self, data: dict, schema_version: str) -> dict:
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

        # Upgrade tiles to data streams
        if session_start_time and session_end_time:
            start_str = (
                session_start_time.isoformat() if hasattr(session_start_time, "isoformat") else str(session_start_time)
            )
            end_str = session_end_time.isoformat() if hasattr(session_end_time, "isoformat") else str(session_end_time)
            data_streams = upgrade_tiles_to_data_stream(
                tiles,
                start_str,
                end_str,
                chamber_immersion=chamber_immersion or {},
                sample_immersion=sample_immersion,
                device_name=instrument_id or "",
                software=software,
            )
            if active_objectives:
                data_streams[0]["active_devices"].extend(active_objectives)
        else:
            # If no session times, create empty data streams
            raise NotImplementedError()

        # Create coordinate system from axes
        coordinate_system = self._create_coordinate_system_from_axes(axes)

        # Upgrade calibrations and maintenance
        upgraded_calibrations = [upgrade_calibration(cal) for cal in calibrations]
        upgraded_maintenance = self._upgrade_maintenance(maintenance)

        # Determine acquisition type
        acquisition_type = self._determine_acquisition_type(data)

        subject_details = AcquisitionSubjectDetails(
            mouse_platform_name="N/A",
        )

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
