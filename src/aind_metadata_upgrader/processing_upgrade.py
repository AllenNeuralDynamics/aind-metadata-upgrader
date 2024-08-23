"""Module to contain code to upgrade old processing models"""

from typing import Union

from aind_data_schema.base import AindModel
from aind_data_schema.core.processing import (
    DataProcess,
    PipelineProcess,
    Processing,
)

from aind_metadata_upgrader.base_upgrade import BaseModelUpgrade
from aind_metadata_upgrader.utils import construct_new_model


class DataProcessUpgrade(BaseModelUpgrade):
    """Handle upgrades for DataProcess class"""

    def __init__(self, old_data_process_dict: Union[dict, DataProcess]):
        """
        Handle mapping of old DataProcess models into current models

        Parameters
        ----------
        old_data_process_dict : dict
        """
        super().__init__(old_model=old_data_process_dict, model_class=DataProcess)

    def upgrade(self, **kwargs) -> AindModel:
        """Upgrades the old model into the current version"""
        version = self._get_or_default(self.old_model_dict, "version", kwargs)
        software_version = self._get_or_default(self.old_model_dict, "software_version", kwargs)
        if version is not None and software_version is None:
            self.old_model_dict["software_version"] = version
            del self.old_model_dict["version"]
        # Empty notes with 'Other' name is not allowed in the new schema
        name = self._get_or_default(self.old_model_dict, "name", kwargs)
        notes = self._get_or_default(self.old_model_dict, "notes", kwargs)
        outputs = self._get_or_default(self.old_model_dict, "outputs", kwargs)

        if name == "Other" and notes is None:
            self.old_model_dict["notes"] = "missing notes"
        # this takes care of setting the outputs to an empty dict (default) if it is None
        self.old_model_dict["outputs"] = outputs

        return construct_new_model(self.old_model_dict, DataProcess, self.allow_validation_errors)


class ProcessingUpgrade(BaseModelUpgrade):
    """Handle upgrades for Processing class"""

    def __init__(self, old_processing_model: Processing):
        """
        Handle mapping of old Processing models into current models

        Parameters
        ----------
        old_processing_model : Processing
            The old model to upgrade
        """
        super().__init__(old_model=old_processing_model, model_class=Processing)

    def upgrade(self, **kwargs) -> AindModel:
        """Upgrades the old model into the current version"""
        # old versions of the schema (<0.3.0) had data_processes directly
        schema_version = self.old_model_dict.get("schema_version")
        if schema_version is None or schema_version < "0.3.0":
            data_processes = self._get_or_default(self.old_model_dict, "data_processes", kwargs)
            pipeline_version = self._get_or_default(self.old_model_dict, "pipeline_version", kwargs)
            pipeline_url = self._get_or_default(self.old_model_dict, "pipeline_version", kwargs)

            if data_processes is not None:
                # upgrade data processes
                data_processes_new = [DataProcessUpgrade(data_process).upgrade() for data_process in data_processes]
                processor_full_name = kwargs.get("processor_full_name")
                processing_pipeline = PipelineProcess(
                    pipeline_version=pipeline_version,
                    pipeline_url=pipeline_url,
                    data_processes=data_processes_new,
                    processor_full_name=processor_full_name,
                )
        else:
            processing_pipeline = self._get_or_default(self.old_model_dict, "processing_pipeline", kwargs)
            # upgrade data processes
            data_processes_new = []
            data_processes_old = processing_pipeline["data_processes"]
            processing_pipeline_dict = processing_pipeline
            for data_process in data_processes_old:
                data_processes_new.append(DataProcessUpgrade(data_process).upgrade())
            processing_pipeline_dict.pop("data_processes")
            processing_pipeline = PipelineProcess(data_processes=data_processes_new, **processing_pipeline_dict)

        return Processing(
            processing_pipeline=processing_pipeline,
            analyses=self._get_or_default(self.old_model_dict, "analyses", kwargs),
            notes=self._get_or_default(self.old_model_dict, "notes", kwargs),
        )
