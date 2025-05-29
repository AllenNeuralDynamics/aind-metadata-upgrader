"""Main entrypoint for upgrader"""

from packaging.version import Version

from aind_data_schema.core.data_description import DataDescription
from aind_data_schema.core.quality_control import QualityControl
from aind_data_schema.core.subject import Subject
from aind_data_schema.core.metadata import CORE_FILES, Metadata
from aind_metadata_upgrader.upgrade_mapping import MAPPING


UPGRADE_VERSIONS = {
    "data_description": DataDescription.model_fields["schema_version"].default,
    "subject": Subject.model_fields["schema_version"].default,
    "quality_control": QualityControl.model_fields["schema_version"].default,
}


class Upgrade:
    """Main entrypoint to the metadata-upgrader"""

    def __init__(self, record: dict):
        """Initialize the upgrader"""

        self.data = record

        core_files = {}
        for core_file in CORE_FILES:
            if core_file in record:
                core_files[core_file] = self.upgrade_core_file(core_file)

        # try:
        #     self.metadata = Metadata(**core_files)
        # except Exception as e:
        #     raise ValueError(f"Failed to validated Metadata: {e}")

    def _try_validate(self, core_file: str, data: dict):
        """Try to validate the core file data against its schema"""
        try:
            if core_file == "data_description":
                return DataDescription(**data)
            elif core_file == "subject":
                return Subject(**data)
            elif core_file == "quality_control":
                return QualityControl(**data)
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

        print(f"Upgrading {core_file}:{core_data['schema_version']} -> {UPGRADE_VERSIONS[core_file]}")

        original_schema_version = Version(core_data["schema_version"])
        upgraded_schema_version = Version(UPGRADE_VERSIONS[core_file])

        upgraded_data = core_data

        if original_schema_version == upgraded_schema_version:
            print(f"No upgrade needed for {core_file} (version {original_schema_version})")
        else:
            # Apply all upgraders (in order) that match the original schema version
            for specifier_set, upgrader in MAPPING[core_file]:
                if original_schema_version in specifier_set:
                    upgraded_data = upgrader().upgrade(upgraded_data, upgraded_schema_version)

        return self._try_validate(core_file, upgraded_data)
