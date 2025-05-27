"""Mapping or core file / version number combinations to their upgrade functions."""

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2

DATA_DESCRIPTION = {
    "1.0.0": DataDescriptionV1V2,
    "1.0.4": DataDescriptionV1V2,
}

MAPPING = {
    "data_description": DATA_DESCRIPTION,
}
