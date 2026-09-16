"""2.x to 3.0 quality control upgrade functions"""

from typing import Optional

from biodata_schema.core.quality_control import QualityControl

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v2v3_utils import recursive_upgrade


def _upgrade_metric(node: dict) -> None:
    """v3 dropped the validator that converted list-valued tags to a dict"""
    tags = node.get("tags")
    if isinstance(tags, list):
        node["tags"] = {f"tag_{i + 1}": tag for i, tag in enumerate(tags)}


def _upgrade_quality_control(node: dict) -> None:
    """v3 dropped the validator that rewrote default_grouping for list-tag metrics"""
    grouping = node.get("default_grouping")
    metrics = node.get("metrics")
    if not grouping or not metrics:
        return
    if all(isinstance(item, str) for item in grouping):
        first_metric = metrics[0]
        if isinstance(first_metric, dict) and isinstance(first_metric.get("tags"), list):
            node["default_grouping"] = [["modality"], ["tag_1"]]


HANDLERS = {
    "Quality control": _upgrade_quality_control,
    "QC metric": _upgrade_metric,
    "Curation metric": _upgrade_metric,
}


class QCUpgraderV2V3(CoreUpgrader):
    """Upgrade quality control core file from v2.x to v3.0"""

    def upgrade(
        self, data: dict, schema_version: str, metadata: Optional[dict] = None, return_model: bool = False
    ) -> dict | QualityControl:
        """Upgrade the quality control data to v3.0"""
        data = recursive_upgrade(data, HANDLERS, object_type="Quality control")
        data["schema_version"] = schema_version
        return QualityControl.model_validate(data) if return_model else data
