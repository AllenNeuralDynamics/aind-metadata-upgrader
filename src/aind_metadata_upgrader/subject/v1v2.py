"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader


class SubjectUpgraderV1V2(CoreUpgrader):
    """Upgrade subject core file from v1.x to v2.0"""

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the subject core file data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
