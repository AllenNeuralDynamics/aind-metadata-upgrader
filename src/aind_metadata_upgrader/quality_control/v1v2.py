"""<=v1.4 to v2.0 quality control upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader

from aind_data_schema.core.quality_control import CurationMetric


class QCUpgraderV1V2(CoreUpgrader):
    """Upgrade quality control core file from v1.x to v2.0"""

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the subject core file data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        data["schema_version"] = schema_version

        # Add "object_type" to all the evaluations and metrics
        for ei, evaluation in enumerate(data.get("evaluations", [])):
            if "object_type" not in evaluation:
                data["evaluations"][ei]["object_type"] = "QC evaluation"

            for mi, metric in enumerate(evaluation.get("metrics", [])):
                if "object_type" not in metric:
                    data["evaluations"][ei]["metrics"][mi]["object_type"] = "QC metric"

        # Handle upgrades to CurationMetric objects
        for ei, evaluation in enumerate(data.get("evaluations", [])):

            for mi, metric in enumerate(evaluation.get("metrics", [])):
                if "type" in metric["value"] and metric["value"]["type"] == "curation":
                    # Bump the CurationMetric object up to the metric level
                    curations = metric["value"]["curations"]

                    new_metric = CurationMetric(
                        name=metric.get("name", "unknown"),
                        value=curations,
                        description=metric.get("description", None),
                        reference=metric.get("reference", None),
                        evaluated_assets=metric.get("evaluated_assets", []),
                        type="unknown",
                        curation_history=metric.get("curation_history", []),
                    )

                    data["evaluations"][ei]["metrics"][mi] = new_metric.model_dump()

        return {
            "object_type": "Quality control",
            **data,
        }
