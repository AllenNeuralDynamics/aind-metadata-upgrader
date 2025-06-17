"""<=v1.4 to v2.0 metadata upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader

from aind_metadata_upgrader.utils.v1v2_utils import remove


class MetadataUpgraderV1V2(CoreUpgrader):
    """Upgrade procedures from v1.4 to v2.0"""

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the metadata to v2.0"""

        data["schema_version"] = schema_version

        remove(data, "id")
        remove(data, "created")
        remove(data, "last_modified")
        data["other_identifiers"] = data.get("external_links", {})
        remove(data, "external_links")

        return data
