"""2.x to 3.0 subject upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade


def _upgrade_breeding_info(node: dict) -> None:
    """BreedingInfo.breeding_group was removed in v3"""
    node.pop("breeding_group", None)


HANDLERS = {
    "Breeding info": _upgrade_breeding_info,
}


class SubjectUpgraderV2V3(CoreUpgrader):
    """Upgrade subject core file from v2.x to v3.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the subject data to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Subject")
        data["schema_version"] = schema_version
        return data
