"""2.x to 3.0 procedures upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade

DEPRECATED_SECTION_FIELDS = (
    "coordinate_system_name",
    "start_coordinate",
    "end_coordinate",
    "thickness",
    "thickness_unit",
    "partial_slice",
)


def _upgrade_section(node: dict) -> None:
    """Sections carrying coordinate data become PlanarSection in v3"""
    if any(node.get(field) is not None for field in DEPRECATED_SECTION_FIELDS):
        node["object_type"] = "Planar section"
    else:
        for field in DEPRECATED_SECTION_FIELDS:
            node.pop(field, None)


HANDLERS = {
    "Section": _upgrade_section,
}


class ProceduresUpgraderV2V3(CoreUpgrader):
    """Upgrade procedures core file from v2.x to v3.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the procedures data to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Procedures")
        data["schema_version"] = schema_version
        return data
