"""2.x to 3.0 instrument upgrade functions"""

from typing import Optional

from biodata_schema.components.geometry import Rectangle

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade


def _upgrade_shape(node: dict) -> None:
    """Enclosure/Arena size + size_unit were replaced by a geometry object"""
    size = node.pop("size", None)
    size_unit = node.pop("size_unit", None)
    if node.get("shape") is not None:
        return
    scale = size.get("scale") if isinstance(size, dict) else None
    if not scale or len(scale) < 2 or not size_unit:
        return
    node["shape"] = Rectangle(width=scale[0], height=scale[1], size_unit=size_unit).model_dump()


def _upgrade_daq_channel(node: dict) -> None:
    """DAQChannel.channel_index was replaced by DAQChannel.port"""
    channel_index = node.pop("channel_index", None)
    if channel_index is not None and node.get("port") is None:
        node["port"] = channel_index


HANDLERS = {
    "Enclosure": _upgrade_shape,
    "Arena": _upgrade_shape,
    "DAQ channel": _upgrade_daq_channel,
}


class InstrumentUpgraderV2V3(CoreUpgrader):
    """Upgrade instrument core file from v2.x to v3.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the instrument data to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Instrument")
        data["schema_version"] = schema_version
        return data
