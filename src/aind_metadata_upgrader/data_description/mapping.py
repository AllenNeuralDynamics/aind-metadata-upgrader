"""Mapping of version numbers to upgraders"""

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2

MAPPING = {
    "1.0.4": DataDescriptionV1V2,
}
