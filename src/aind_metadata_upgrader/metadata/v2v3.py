"""2.x to 3.0 metadata upgrade functions"""

from typing import Optional

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade

# The core file upgraders handle their own deprecated fields; this pass only sweeps the
# document-level fields and anything the core upgraders are not registered for.
HANDLERS = {}


class MetadataUpgraderV2V3(CoreUpgrader):
    """Upgrade metadata from v2.x to v3.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the metadata to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Metadata")
        data["schema_version"] = schema_version
        return data
