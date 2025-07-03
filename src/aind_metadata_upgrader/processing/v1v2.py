"""<=v1.4 to v2.0 processing upgrade functions"""

from aind_data_schema.components.identifiers import Code, Person
from aind_data_schema.core.processing import DataProcess

from aind_metadata_upgrader.base import CoreUpgrader

names = {}


class ProcessingV1V2(CoreUpgrader):
    """Upgrade processing from v1.4 to v2.0"""

    def _create_code_object(self, process_data: dict, parameters=None) -> Code:
        """Create a Code object from V1 process data"""
        return Code(
            name=process_data.get("name", "Unknown"),
            version=process_data.get("code_version", "unknown"),
            url=process_data.get("code_url", ""),
            parameters=process_data.get("parameters", None),
        )

    def _create_person_from_name(self, name: str) -> Person:
        """Create a Person object from a name string"""
        return Person(name=name)

    def _get_process_name(self, name: str) -> str:
        """Get a name for this process, append 1/2/3 for duplicates"""

        if name not in names:
            names[name] = 1
        else:
            names[name] += 1
        return f"{name}_{names[name]}"

    def _convert_v1_process_to_v2(self, process_data: dict, stage: str) -> dict:
        """Convert a V1 process/analysis to V2 DataProcess format"""

        # Create experimenters list
        experimenters = []
        if stage == "Processing":
            # For processing pipeline, get processor_full_name from parent
            pass  # Will be handled in main upgrade method
        elif stage == "Analysis":
            # For analyses, get analyst_full_name
            analyst_name = process_data.get("analyst_full_name")
            if analyst_name:
                experimenters.append(self._create_person_from_name(analyst_name))

        if not experimenters:
            # Default experimenter if none specified
            experimenters.append(Person(name="Unknown"))

        # Move parameters into Code
        output_parameters = process_data.get("outputs", None)

        notes = process_data.get("notes", "")
        if process_data.get("name", "Other") == "Other" and not notes:
            notes = "(v1v2 upgrade) Process type is unknown, no notes were provided."

        v2_process = DataProcess(
            process_type=process_data.get("name", "Unknown"),
            name=self._get_process_name(process_data.get("name", "Unknown")),
            stage=stage,
            code=self._create_code_object(process_data),
            experimenters=experimenters,
            pipeline_name=None,  # Will be set if there's a pipeline
            start_date_time=process_data.get("start_date_time"),
            end_date_time=process_data.get("end_date_time"),
            output_path=process_data.get("output_location"),  # Map output_location to output_path
            output_parameters=output_parameters if output_parameters else {},
            notes=notes,
            resources=process_data.get("resources"),  # ResourceUsage structure is compatible
        )

        return v2_process.model_dump()

    def _convert_pipeline_processes(self, pipeline_processes: list, processor_name: str, v2_data: dict) -> None:
        """Convert processing pipeline processes to V2 format"""
        for process_data in pipeline_processes:
            v2_process = self._convert_v1_process_to_v2(process_data, "Processing")
            # Set experimenter to processor from pipeline
            v2_process["experimenters"] = [self._create_person_from_name(processor_name)]
            # Set pipeline name if pipeline exists
            if v2_data["pipelines"]:
                v2_process["pipeline_name"] = "Processing Pipeline"
            v2_data["data_processes"].append(v2_process)

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the processing to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Initialize the V2 structure
        v2_data = {
            "schema_version": schema_version,
            "data_processes": [],
            "pipelines": None,
            "notes": data.get("notes"),
            "dependency_graph": {},
        }

        # Process the processing_pipeline section
        processing_pipeline = data.get("processing_pipeline", {})
        pipeline_processes = processing_pipeline.get("data_processes", [])
        processor_name = processing_pipeline.get("processor_full_name", "Unknown")

        # Create pipeline if it exists
        pipeline_url = processing_pipeline.get("pipeline_url")
        pipeline_version = processing_pipeline.get("pipeline_version")
        if processing_pipeline and (pipeline_url or pipeline_version):
            pipeline_code = Code(
                name="Processing Pipeline", version=pipeline_version or "unknown", url=pipeline_url or ""
            )
            v2_data["pipelines"] = [pipeline_code]

        # Convert processing pipeline processes
        self._convert_pipeline_processes(pipeline_processes, processor_name, v2_data)

        # Convert analyses
        analyses = data.get("analyses", [])
        seen_names = set(process["name"] for process in v2_data["data_processes"])

        if analyses:
            for i, analysis_data in enumerate(analyses):
                v2_process = self._convert_v1_process_to_v2(analysis_data, "Analysis")

                # Handle duplicate names by adding suffix
                original_name = v2_process["name"]
                if original_name in seen_names:
                    counter = 1
                    while f"{original_name}_{counter}" in seen_names:
                        counter += 1
                    v2_process["name"] = f"{original_name}_{counter}"

                seen_names.add(v2_process["name"])
                v2_data["data_processes"].append(v2_process)

        # Create dependency graph - sequential processing
        dependency_graph = {}
        for i, process in enumerate(v2_data["data_processes"]):
            process_name = process["name"]
            if i == 0:
                dependency_graph[process_name] = []
            else:
                # Each process depends on the previous one
                dependency_graph[process_name] = [v2_data["data_processes"][i - 1]["name"]]

        v2_data["dependency_graph"] = dependency_graph

        return v2_data
