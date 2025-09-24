"""<=v1.4 to v2.0 data description upgrade functions"""

from typing import Optional
from aind_data_schema.components.identifiers import Person
from aind_data_schema.core.data_description import Funding
from aind_data_schema_models.licenses import License
from aind_data_schema_models.organizations import Organization

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.settings import FAKE_MISSING_DATA
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_v1_modalities, upgrade_registry

from aind_data_access_api.document_db import MetadataDbClient


client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v1",
)


class DataDescriptionV1V2(CoreUpgrader):
    """Upgrade data description from v1.4 to v2.0"""

    def _process_comma_separated_funders(self, funder: str, fundee, grant_number) -> list:
        """Process comma-separated funders into separate funding sources"""
        result = []
        fundee_list = fundee
        if isinstance(fundee_list, str):
            fundee_list = [name.strip() for name in fundee_list.split(",")]
        elif not isinstance(fundee_list, list):
            fundee_list = ["unknown"]

        for funder_name in funder.split(","):
            result.append(
                Funding(
                    funder=Organization.from_name(funder_name.strip()),
                    fundee=[Person(name=f) for f in fundee_list],
                    grant_number=grant_number,
                ).model_dump()
            )
        return result

    def _upgrade_funder(self, funder: str):
        """Upgrade a single funder string to an Organization."""
        if isinstance(funder, str):
            if funder == "AIND":
                return Organization.AI
            else:
                return Organization.from_name(funder)
        elif isinstance(funder, dict):
            # Replace AIND with AI if you see it
            if funder.get("name") == "Allen Institute for Neural Dynamics":
                return Organization.AI
            return Organization.from_name(funder.get("name", "Allen Institute"))
        else:
            return None

    def _get_funding_source(self, data: dict) -> list:
        """Get and upgrade funding source information from the data dictionary."""

        funding_source = data.get("funding_source", [])

        # Handle empty funding source
        if not funding_source:
            if FAKE_MISSING_DATA:
                return [Funding(funder=Organization.AI, fundee=[Person(name="unknown")]).model_dump()]
            return []

        # Process each funding source
        result_funding_sources = []
        for funding in funding_source:
            funder = funding.get("funder", None)
            fundee = funding.get("fundee", [])
            grant_number = funding.get("grant_number", None)

            # Handle funder - can be string (possibly comma-separated) or dict
            if isinstance(funder, str) and "," in funder:
                # Split comma-separated funders into separate funding sources
                result_funding_sources.extend(self._process_comma_separated_funders(funder, fundee, grant_number))
            else:
                funder_org = self._upgrade_funder(funder)

                if not funder_org:
                    raise ValueError(f"Unsupported funder type: {funder}")

                # Handle fundee - can be string (comma-separated) or list
                if isinstance(fundee, str):
                    if fundee:
                        fundee_list = [Person(name=name.strip()) for name in fundee.split(",")]
                    else:
                        fundee_list = [Person(name="unknown")]
                elif isinstance(fundee, list):
                    fundee_list = [Person(name=f) for f in fundee]
                else:
                    fundee_list = [Person(name="unknown")]

                result_funding_sources.append(
                    Funding(
                        funder=funder_org,
                        fundee=fundee_list,
                        grant_number=grant_number,
                    ).model_dump()
                )

        return result_funding_sources

    def _get_investigators(self, data: dict) -> list:
        """Build investigators list"""
        investigators = data.get("investigators", [])
        for i, investigator in enumerate(investigators):
            # Convert from PIDName to Person
            if not isinstance(investigator, Person):
                investigators[i] = Person(
                    name=investigator["name"],
                )
        return investigators

    def _get_creation_time(self, data: dict) -> str | None:
        """Handle old records that have both creation_date and creation_time"""
        # If only creation_time exists, return that
        if "creation_time" in data and "creation_date" not in data:
            return data["creation_time"]
        elif "creation_date" in data and "creation_time" in data:
            creation_datetime = data["creation_date"] + "T" + data["creation_time"]
        else:
            creation_datetime = data.get("creation_date", None)

        return creation_datetime

    def _get_institution(self, data: dict):
        """Handle old records that have institution as a string"""
        institution = data.get("institution", None)
        if isinstance(institution, str):
            try:
                return Organization.from_abbreviation(institution)
            except ValueError:
                raise ValueError(f"Unsupported institution abbreviation: {institution}")
        if institution:
            institution = upgrade_registry(institution)
        return institution

    def _get_data_level(self, data: dict) -> str | None:
        """Handle old data_level types"""
        data_level = data.get("data_level", None)
        if data_level:
            if "raw" in data_level.lower():
                return "raw"
            elif "derived" in data_level.lower():
                return "derived"
        return data_level

    def _get_project_name(self, data: dict) -> str:
        """Handle missing project_name"""
        project_name = data.get("project_name", "unknown")
        if not project_name:
            project_name = "unknown"
        return project_name

    def _ensure_investigators_exist(self, investigators: list) -> list:
        """Ensure at least one investigator exists"""
        if len(investigators) == 0:
            investigators.append(Person(name="unknown"))
        return investigators

    def _build_output_dict(self, data: dict, schema_version: str, source_data: Optional[list] = None, **kwargs) -> dict:
        """Build the output dictionary with all upgraded fields"""
        return {
            "schema_version": schema_version,
            "license": data.get("license", License.CC_BY_40),
            "subject_id": data.get("subject_id", None),
            "creation_time": kwargs.get("creation_time"),
            "tags": None,  # Set to None as specified in the original
            "name": data.get("name", None),
            "institution": kwargs.get("institution"),
            "funding_source": kwargs.get("funding_source"),
            "data_level": kwargs.get("data_level"),
            "group": data.get("group", None),
            "investigators": kwargs.get("investigators"),
            "project_name": kwargs.get("project_name"),
            "restrictions": data.get("restrictions", None),
            "modalities": kwargs.get("modalities"),
            "data_summary": data.get("data_summary", None),
            "source_data": source_data,
            "object_type": "Data description",
        }

    def _upgrade_source_data(self, data: dict) -> Optional[list]:
        """Upgrade the source_data field for v2.0"""

        # If this is raw data, return None
        if "raw" in data.get("data_level", "").lower():
            return None

        # Derived asset -- if we have input_data_name, use that
        if "input_data_name" in data and data["input_data_name"]:
            input_name = data["input_data_name"]
            # Check if this name is derived (more than 4 parts)
            if len(input_name.split("_")) > 4:
                # Use the client to get the parent asset's input_data_name and chain up until we reach raw data
                input_names = [input_name]
                prev_data_description = client.retrieve_docdb_records(
                    filter_query={"data_description.name": input_name},
                    projection={"data_description": 1},
                    limit=1,
                )[0]
                while "raw" not in prev_data_description.get("data_description", {}).get("data_level", "").lower():
                    # Add to the start of the list the name and get the next parent
                    next_input_name = prev_data_description.get("data_description", {}).get("input_data_name", None)
                    input_names.insert(0, next_input_name)
                    prev_data_description = client.retrieve_docdb_records(
                        filter_query={"data_description.name": next_input_name},
                        limit=1,
                    )[0]

                # Insert the raw data name at the start
                raw_data_name = prev_data_description.get("data_description", {}).get("name", None)
                input_names.insert(0, raw_data_name)
                return input_names
            else:
                return [input_name]
        else:
            input_from_name = data.get("name").split("_")[:4]  # get the original name parts
            input_name = "_".join(input_from_name)
            print(f"Derived data without input_data_name, using name to infer input: {input_name}")
            return [input_name]

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the data description to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Get upgraded field values using helper methods
        funding_source = self._get_funding_source(data)
        creation_time = self._get_creation_time(data)
        institution = self._get_institution(data)
        data_level = self._get_data_level(data)
        project_name = self._get_project_name(data)
        investigators = self._get_investigators(data)
        investigators = self._ensure_investigators_exist(investigators)
        modalities = upgrade_v1_modalities(data)

        # Upgrade the new source_data field for 2.0
        source_data = self._upgrade_source_data(data)

        # Build and return the upgraded output
        return self._build_output_dict(
            data,
            source_data=source_data,
            schema_version=schema_version,
            funding_source=funding_source,
            creation_time=creation_time,
            institution=institution,
            data_level=data_level,
            project_name=project_name,
            investigators=investigators,
            modalities=modalities,
        )
