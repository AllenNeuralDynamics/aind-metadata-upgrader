"""Main entrypoint for upgrader"""

from aind_data_schema.core.data_description import DataDescription
from aind_metadata_upgrader.upgrade_mapping import MAPPING


class Upgrade():
    """Main entrypoint to the metadata-upgrader"""

    def __init__(self, record: dict):
        """Initialize the upgrader"""

        self.data = record
        self.upgrade_core_file("data_description")

    def upgrade_core_file(self, core_file: str):
        """Initialize one core file"""

        if core_file not in self.data:
            raise ValueError(f"Core file '{core_file}' not found in record")

        core_data = self.data[core_file]

        print(f"Upgrading {core_file}:{core_data['schema_version']} -> {DataDescription.__fields__['schema_version'].default}")

        original_schema_version = core_data["schema_version"]
        upgraded_schema_version = DataDescription.__fields__["schema_version"].default

        if original_schema_version == upgraded_schema_version:
            print(f"No upgrade needed for {core_file} (version {original_schema_version})")
            upgraded_data = core_data
        else:
            upgrader = MAPPING[core_file][original_schema_version]()
            upgraded_data = upgrader.upgrade(core_data, upgraded_schema_version)

        if core_file == "data_description":
            try:
                self.output = DataDescription(**upgraded_data)
            except Exception as e:
                raise ValueError(f"Failed to validate upgraded data description: {e}")
