"""<=v1.4 to v2.0 acquisition upgrade functions"""

from typing import Dict, List, Optional
from aind_data_schema.components.identifiers import Person
from aind_data_schema.components.coordinates import CoordinateSystem
from aind_data_schema.core.acquisition import AcquisitionSubjectDetails
from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.acquisition.v1v2_tiles import upgrade_tiles_to_data_streams


class AcquisitionV1V2(CoreUpgrader):
    """Upgrade acquisition from v1.4 to v2.0"""

    def _upgrade_experimenter_names_to_persons(self, experimenter_names: List[str]) -> List[Dict]:
        """Convert experimenter full names to Person objects"""
        experimenters = []
        for name in experimenter_names:
            if name and name.strip():
                experimenters.append(Person(name=name.strip()).model_dump())
        return experimenters

    def _upgrade_calibrations(self, calibrations: List[Dict]) -> List[Dict]:
        """Upgrade calibration objects"""
        upgraded_calibrations = []
        for cal in calibrations:
            if cal:
                # Remove any fields that don't belong in v2 calibrations
                # The calibration structure should already be mostly compatible
                upgraded_calibrations.append(cal)
        return upgraded_calibrations

    def _upgrade_maintenance(self, maintenance: List[Dict]) -> List[Dict]:
        """Upgrade maintenance objects"""
        upgraded_maintenance = []
        for maint in maintenance:
            if maint:
                # The maintenance structure should already be mostly compatible
                upgraded_maintenance.append(maint)
        return upgraded_maintenance

    def _create_coordinate_system_from_axes(self, axes: List[Dict]) -> Optional[Dict]:
        """Create coordinate system from V1 axes information"""
        if not axes:
            return None

        # For now, return None and let the system use defaults
        # In a more sophisticated implementation, you could construct a coordinate system
        # from the axis information
        return None

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

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the acquisition data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Extract V1 fields
        protocol_id = data.get("protocol_id", [])
        experimenter_full_name = data.get("experimenter_full_name", [])
        specimen_id = data.get("specimen_id")
        subject_id = data.get("subject_id")
        instrument_id = data.get("instrument_id")
        calibrations = data.get("calibrations", [])
        maintenance = data.get("maintenance", [])
        session_start_time = data.get("session_start_time")
        session_end_time = data.get("session_end_time")
        tiles = data.get("tiles", [])
        axes = data.get("axes", [])
        notes = data.get("notes")

        # Fields that are removed in V2 (just for documentation):
        # - chamber_immersion, sample_immersion
        # - active_objectives
        # - local_storage_directory, external_storage_directory
        # - processing_steps
        # - software
        chamber_immersion = data.get("chamber_immersion")
        sample_immersion = data.get("sample_immersion")

        # Upgrade experimenter names to Person objects
        experimenters = self._upgrade_experimenter_names_to_persons(experimenter_full_name)

        # Upgrade tiles to data streams
        if session_start_time and session_end_time:
            data_streams = upgrade_tiles_to_data_streams(
                tiles,
                session_start_time,
                session_end_time,
                chamber_immersion=chamber_immersion,
                sample_immersion=sample_immersion,
                device_name=instrument_id,
            )
        else:
            # If no session times, create empty data streams
            data_streams = []

        # Create coordinate system from axes
        coordinate_system = self._create_coordinate_system_from_axes(axes)

        # Upgrade calibrations and maintenance
        upgraded_calibrations = self._upgrade_calibrations(calibrations)
        upgraded_maintenance = self._upgrade_maintenance(maintenance)

        # Determine acquisition type
        acquisition_type = self._determine_acquisition_type(data)

        subject_details = AcquisitionSubjectDetails()

        # Build V2 acquisition object
        output = {
            "schema_version": schema_version,
            "subject_id": subject_id,
            "specimen_id": specimen_id,
            "acquisition_start_time": session_start_time,
            "acquisition_end_time": session_end_time,
            "experimenters": experimenters,
            "protocol_id": protocol_id if protocol_id else None,
            "ethics_review_id": None,  # New field in V2, not available in V1
            "instrument_id": instrument_id,
            "acquisition_type": acquisition_type,
            "notes": notes,
            "coordinate_system": coordinate_system,
            "calibrations": upgraded_calibrations,
            "maintenance": upgraded_maintenance,
            "data_streams": data_streams,
            "stimulus_epochs": [],  # New field in V2, not available in V1
            "subject_details": None,  # New field in V2, not available in V1
        }

        return output
