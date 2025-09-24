"""Main entrypoint for upgrader"""

import traceback
import copy

from aind_data_schema.core.acquisition import Acquisition
from aind_data_schema.core.data_description import DataDescription
from aind_data_schema.core.instrument import Instrument
from aind_data_schema.core.metadata import Metadata
from aind_data_schema.core.procedures import Procedures
from aind_data_schema.core.processing import Processing
from aind_data_schema.core.quality_control import QualityControl
from aind_data_schema.core.subject import Subject
from aind_data_schema.core.metadata import REQUIRED_FILE_SETS
from packaging.version import Version

from aind_metadata_upgrader.upgrade_mapping import MAPPING
from aind_metadata_upgrader.utils.v1v2_metadata_utils import repair_metadata

CORE_FILES = [
    "subject",
    "data_description",
    "procedures",
    "instrument",
    "processing",
    "acquisition",
    "quality_control",
    "model",
    "rig",
    "session",
]

UPGRADE_VERSIONS = {
    "data_description": DataDescription.model_fields["schema_version"].default,
    "instrument": Instrument.model_fields["schema_version"].default,
    "subject": Subject.model_fields["schema_version"].default,
    "quality_control": QualityControl.model_fields["schema_version"].default,
    "rig": Instrument.model_fields["schema_version"].default,
    "processing": Processing.model_fields["schema_version"].default,
    "procedures": Procedures.model_fields["schema_version"].default,
    "acquisition": Acquisition.model_fields["schema_version"].default,
    "session": Acquisition.model_fields["schema_version"].default,
    "metadata": Metadata.model_fields["schema_version"].default,
}

TYPE_MAPPING = {
    "data_description": DataDescription,
    "instrument": Instrument,
    "subject": Subject,
    "quality_control": QualityControl,
    "rig": Instrument,
    "processing": Processing,
    "procedures": Procedures,
    "acquisition": Acquisition,
    "session": Acquisition,
    "metadata": Metadata,
}

CORE_MAPPING = {
    "rig": "instrument",
    "session": "acquisition",
}


class Upgrade:
    """Main entrypoint to the metadata-upgrader"""

    def __init__(self, record: dict, skip_metadata_validation: bool = False):
        """Initialize the upgrader"""

        self.data = record
        self.raw_data = copy.deepcopy(record)  # Keep a copy of the original data
        self.skip_metadata_validation = skip_metadata_validation

        # Figure out what core files we have, and what outputs we expected
        expected_core_files = self._determine_expected_core_files()

        core_files = self._process_core_files()

        self._validate_required_files(core_files)

        self.upgrade_metadata(core_files)

        for expected_core_file in expected_core_files:
            if not hasattr(self.metadata, expected_core_file) or getattr(self.metadata, expected_core_file) is None:
                raise ValueError(f"Expected core file '{expected_core_file}' not found in upgraded metadata")

    def _determine_expected_core_files(self) -> list:
        """Determine what core files we have and what outputs we expect"""
        expected_core_files = []
        for core_file in CORE_FILES:
            if core_file in self.data and self.data[core_file]:
                # We have data for this file
                expected_core_files.append(CORE_MAPPING.get(core_file, core_file))
        return expected_core_files

    def _process_core_files(self) -> dict:
        """Process all available core files"""
        core_files = {}
        for core_file in CORE_FILES:
            if core_file in self.data and self.data[core_file]:
                target_key = CORE_MAPPING.get(core_file, core_file)

                # Only process if we haven't already processed the target key
                if target_key not in core_files:
                    core_files[target_key] = self.upgrade_core_file(core_file)
        return core_files

    def _validate_required_files(self, core_files: dict):
        """Validate that all required core files are present"""
        if not self.skip_metadata_validation:
            # Check that at least one of the required file sets is present
            if not any(file in core_files for file in REQUIRED_FILE_SETS):
                raise ValueError(
                    "No required core files found. At least one of the required file sets must be present. "
                    "This asset cannot be upgraded."
                )

            for trigger_file, required_files in REQUIRED_FILE_SETS.items():
                if trigger_file in core_files.keys():
                    if not all(
                        required_file in core_files and core_files[required_file] is not None
                        for required_file in required_files
                    ):
                        raise ValueError(
                            f"All required core files {required_files} were not found. This asset cannot be upgraded."
                        )

    def save(self):
        """Save the upgraded metadata to a standard file"""
        self.metadata.write_standard_file()

    def _try_validate(self, core_file: str, data: dict):
        """Try to validate the core file data against its schema"""
        try:
            if core_file not in TYPE_MAPPING:
                raise ValueError(f"Core file '{core_file}' is not recognized for validation")

            return TYPE_MAPPING[core_file].model_validate(data).model_dump()
        except Exception as e:
            traceback.print_exc()
            raise ValueError(f"Failed to validate {core_file}: {e}")

    def upgrade_metadata(self, new_core_files: dict):
        """Use the metadata upgrader to upgrade and validate the metadata"""

        original_metadata_version = Version(self.data.get("schema_version", "0.0.0"))

        upgraded_data = self.data.copy()
        for core_file in CORE_FILES:
            if core_file in upgraded_data:
                del upgraded_data[core_file]  # Remove core files from the original data
        upgraded_data.update(new_core_files)  # Add upgraded core files

        if self.skip_metadata_validation:
            self.metadata = Metadata.model_construct(**upgraded_data)
            return

        for specifier_set, upgrader in MAPPING["metadata"]:
            if original_metadata_version in specifier_set:
                upgraded_data = upgrader().upgrade(upgraded_data, UPGRADE_VERSIONS["metadata"])

        metadata = repair_metadata(upgraded_data)

        try:
            self.metadata = Metadata(**metadata)
        except Exception as e:
            raise ValueError(f"Failed to validate Metadata: {e}")

    def upgrade_core_file(self, core_file: str):
        """Initialize one core file"""

        if core_file not in self.data:
            raise ValueError(f"Core file '{core_file}' not found in record")

        core_data = self.data[core_file].copy()  # Make a copy to avoid modifying the original data

        if not core_data:
            print(f"No data found for {core_file}, skipping upgrade")
            return None

        if "schema_version" in core_data:
            original_schema_version = Version(core_data["schema_version"])
        else:
            original_schema_version = Version("0.0.0")  # Default to 0.0.0 if not present
        upgraded_schema_version = Version(UPGRADE_VERSIONS[core_file])

        print(f"Upgrading {core_file}:{original_schema_version} -> {upgraded_schema_version}")

        if original_schema_version == upgraded_schema_version:
            print(f"No upgrade needed for {core_file} (version {original_schema_version})")
        else:
            # Apply all upgraders (in order) that match the original schema version
            for specifier_set, upgrader in MAPPING[core_file]:
                if original_schema_version in specifier_set:
                    upgraded_data = upgrader().upgrade(core_data, upgraded_schema_version, metadata=self.raw_data)

        return self._try_validate(core_file, upgraded_data)
