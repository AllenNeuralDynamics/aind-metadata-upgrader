"""<=v1.4 to v2.0 quality control upgrade functions"""

from datetime import datetime
from typing import Optional
from aind_data_schema.core.quality_control import CurationMetric, QCMetric, CurationHistory

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.utils.v1v2_utils import remove


def _handle_dropdown_metric(data: dict) -> dict:
    """Handle dropdown type metric validation"""
    options = data.get("options", [])
    value = data.get("value", None)

    # If someone gave us a list of values (which is wrong), take the first one
    if isinstance(value, list):
        value = value[0] if len(value) > 0 else None

    if value in options:
        data["value"] = value
    if value not in options:
        data["value"] = None

    return data


def _handle_checkbox_metric(data: dict) -> dict:
    """Handle checkbox type metric validation"""
    options = data.get("options", [])
    value = data.get("value", [])

    if not isinstance(value, list):
        value = [value]
        data["value"] = value

    if not all(v in options for v in value):
        # Remove invalid values
        new_values = []
        for v in value:
            if v in options:
                new_values.append(v)
        data["value"] = new_values

    return data


def upgrade_qcportal_metric_value(data: Optional[dict]) -> Optional[dict]:
    """Upgrade custom qcportal-schema metrics, fixing their values if needed"""

    if not data or not isinstance(data, dict) or "type" not in data:
        return data  # Not a qcportal metric, nothing to do

    if data["type"] == "dropdown":
        return _handle_dropdown_metric(data)
    elif data["type"] == "checkbox":
        return _handle_checkbox_metric(data)

    return data


def upgrade_metric(data: dict, modality: dict, stage: str, tags: list) -> dict:
    """Upgrade a metric to the new format"""
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    value = upgrade_qcportal_metric_value(data.get("value", None))

    metric = QCMetric(
        name=data.get("name", "unknown"),
        modality=modality,
        stage=stage,
        value=value,
        status_history=data.get("status_history", []),
        description=data.get("description", None),
        reference=data.get("reference", None),
        tags=tags,
        evaluated_assets=data.get("evaluated_assets", []),
    )

    return metric.model_dump()


def upgrade_curation_metric(data: dict, modality: dict, stage: str, tags: list) -> dict:
    """Upgrade a curation metric to the new format"""

    curations = data["value"]["curations"]
    if not isinstance(curations, list):
        curations = [curations]
    curation_history = data["value"].get("curation_history", [])

    if len(curation_history) == 0:
        curation_history.append(CurationHistory(curator="unknown", timestamp=datetime.now().isoformat()))

    metric = CurationMetric(
        name=data.get("name", "unknown"),
        modality=modality,
        stage=stage,
        tags=tags,
        value=curations,
        description=data.get("description", None),
        reference=data.get("reference", None),
        evaluated_assets=data.get("evaluated_assets", []),
        type="(v1v2 upgrade) type did not exist in v1",
        status_history=data.get("status_history", []),
        curation_history=curation_history,
    )

    return metric.model_dump()


class QCUpgraderV1V2(CoreUpgrader):
    """Upgrade quality control core file from v1.x to v2.0"""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the subject core file data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        data["schema_version"] = schema_version

        metrics = []
        default_grouping = []

        # Add "object_type" to all the evaluations and metrics
        for ei, evaluation in enumerate(data.get("evaluations", [])):

            modality = evaluation.get("modality", {})
            stage = evaluation.get("stage", "unknown")
            tags = [evaluation["name"]]
            default_grouping.append(evaluation["name"])  # Use original evaluations as default grouping

            for metric in evaluation.get("metrics", []):
                if isinstance(metric.get("value"), dict) and metric.get("value", {}).get("type", None) == "curation":
                    # CurationMetric, we'll deal with this in a second
                    metric_data = upgrade_curation_metric(
                        data=metric,
                        modality=modality,
                        stage=stage,
                        tags=tags,
                    )
                else:
                    metric_data = upgrade_metric(
                        data=metric,
                        modality=modality,
                        stage=stage,
                        tags=tags,
                    )
                metrics.append(metric_data)

        remove(data, "evaluations")

        return {
            "object_type": "Quality control",
            "metrics": metrics,
            "default_grouping": default_grouping,
            "notes": data.get("notes", None),
        }
