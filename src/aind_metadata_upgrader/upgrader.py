"""General upgrader for AIND metadata files."""
from aind_data_schema.core.metadata import Metadata


class Upgrader():
    """General upgrader for AIND metadata files

    Currently handles v1 -> v2 upgrades"""

    def __init__(self, data: dict):
        self.data = data

    def upgrade(self) -> Metadata:
        """Run the appropriate upgraders based on the version number of the metadata"""
        version = self.data["schema_version"]
        major_version = int(version.split(".")[0])
        minor_version = int(version.split(".")[1])
        patch_version = int(version.split(".")[2])

        if major_version < 2:
            self.merge_instrument_rig()

        return Metadata()

    def merge_instrument_rig(self):
        """Merge the instrument and rig metadata
        """
        pass