"""<=v1.4 to v2.0 quality control upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader
from aind_data_schema.core.quality_control import QCMetric, CurationMetric

from aind_metadata_upgrader.utils.v1v2_utils import remove


def upgrade_metric(data: dict, modality: dict, stage: str, tags: list) -> dict:
    """Upgrade a metric to the new format"""
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    metric = QCMetric(
        name=data.get("name", "unknown"),
        modality=modality,
        stage=stage,
        value=data.get("value", None),
        status_history=data.get("status_history", []),
        description=data.get("description", None),
        reference=data.get("reference", None),
        tags=tags,
        evaluated_assets=data.get("evaluated_assets", []),
    )

    return metric.model_dump()


def upgrade_curation_metric(data: dict, modality: dict, stage: str, tags: list) -> dict:
    """Upgrade a curation metric to the new format"""
    if not type == "curation":
        raise ValueError(f"Expected type 'curation', got {data.get('type', 'unknown')}")

    curations = data["value"]["curations"]
    curation_history = data["value"].get("curation_history", [])

    metric = CurationMetric(
        name=data.get("name", "unknown"),
        modality=modality,
        stage=stage,
        tags=tags,
        value=curations,
        description=data.get("description", None),
        reference=data.get("reference", None),
        evaluated_assets=data.get("evaluated_assets", []),
        type="unknown",
        curation_history=curation_history,
    )
    
    return metric.model_dump()


class QCUpgraderV1V2(CoreUpgrader):
    """Upgrade quality control core file from v1.x to v2.0"""

    def upgrade(self, data: dict, schema_version: str) -> dict:
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
                if "type" in metric:
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
            **data,
        }
