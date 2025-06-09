"""Main entrypoint for upgrader"""

from aind_data_schema.core.data_description import DataDescription
from aind_data_schema.core.instrument import Instrument

# from aind_data_schema.core.metadata import Metadata
from aind_data_schema.core.processing import Processing
from aind_data_schema.core.quality_control import QualityControl
from aind_data_schema.core.procedures import Procedures
from aind_data_schema.core.subject import Subject
from packaging.version import Version

from aind_metadata_upgrader.upgrade_mapping import MAPPING

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
}

CORE_MAPPING = {
    "rig": "instrument",
    "session": "acquisition",
}


class Upgrade:
    """Main entrypoint to the metadata-upgrader"""

    def __init__(self, record: dict):
        """Initialize the upgrader"""

        self.data = record

        core_files = {}
        for core_file in CORE_FILES:
            if core_file in record:
                core_files[CORE_MAPPING[core_file] if core_file in CORE_MAPPING.keys() else core_file] = (
                    self.upgrade_core_file(core_file)
                )

        # try:
        #     self.metadata = Metadata(**core_files)
        # except Exception as e:
        #     raise ValueError(f"Failed to validated Metadata: {e}")

    def save(self):
        """Save the upgraded metadata to a standard file"""
        self.metadata.write_standard_file()

    def _try_validate(self, core_file: str, data: dict):
        """Try to validate the core file data against its schema"""
        try:
            if core_file == "data_description":
                return DataDescription(**data)
            elif core_file == "subject":
                return Subject(**data)
            elif core_file == "quality_control":
                return QualityControl(**data)
            elif core_file == "instrument":
                return Instrument(**data)
            elif core_file == "rig":
                return Instrument(**data)
            elif core_file == "processing":
                return Processing(**data)
            elif core_file == "procedures":
                return Procedures(**data)
            else:
                raise ValueError(f"Unknown core file type: {core_file}")
        except Exception as e:
            raise ValueError(f"Failed to validate {core_file}: {e}")

    def upgrade_core_file(self, core_file: str):
        """Initialize one core file"""

        if core_file not in self.data:
            raise ValueError(f"Core file '{core_file}' not found in record")

        if core_file not in UPGRADE_VERSIONS:
            print(f"Skipping upgrade for {core_file} (not in UPGRADE_VERSIONS)")
            return {}  # [TODO: Remove when all core files are upgradeable]

        core_data = self.data[core_file]

        if not core_data:
            print(f"No data found for {core_file}, skipping upgrade")
            return None

        if "schema_version" in core_data:
            original_schema_version = Version(core_data["schema_version"])
        else:
            original_schema_version = Version("0.0.0")  # Default to 0.0.0 if not present
        upgraded_schema_version = Version(UPGRADE_VERSIONS[core_file])

        print(f"Upgrading {core_file}:{original_schema_version} -> {upgraded_schema_version}")

        upgraded_data = core_data

        if original_schema_version == upgraded_schema_version:
            print(f"No upgrade needed for {core_file} (version {original_schema_version})")
        else:
            # Apply all upgraders (in order) that match the original schema version
            for specifier_set, upgrader in MAPPING[core_file]:
                if original_schema_version in specifier_set:
                    upgraded_data = upgrader().upgrade(upgraded_data, upgraded_schema_version)

        return self._try_validate(core_file, upgraded_data)
