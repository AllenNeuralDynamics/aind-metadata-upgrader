"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader


class DataDescriptionV1V2(CoreUpgrader):
    """Upgrade data description from v1.4 to v2.0"""

    def upgrade(self, data: dict) -> dict:
        """Upgrade the data description to v2.0"""
        
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # removed fields:
        # platform
        # label
        # related_data
        
        modalities = data.get("modality")
        if isinstance(modalities, str):
            modalities = [modalities]

        output = {
            # new fields in v2
            "schema_version": "2.0.0",
            "object_type": "Data description",
            "tags": None,
            "modalities": modalities,
            "data_level": data.get("data_level", None),
        }

        return data