"""2.x to 3.0 acquisition upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade

HANDLERS = {}


class AcquisitionUpgraderV2V3(CoreUpgrader):
    """Upgrade acquisition core file from v2.x to v3.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the acquisition data to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Acquisition")
        data["schema_version"] = schema_version
        return data
