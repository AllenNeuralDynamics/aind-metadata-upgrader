"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_data_schema.components.identifiers import Person
from aind_data_schema.core.data_description import Funding
from aind_data_schema_models.licenses import License
from aind_data_schema_models.organizations import Organization

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.settings import FAKE_MISSING_DATA
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_v1_modalities


class DataDescriptionV1V2(CoreUpgrader):
    """Upgrade data description from v1.4 to v2.0"""

    def _get_funding_source(self, data: dict) -> list:
        """Get and upgrade funding source information from the data dictionary."""

        funding_source = data.get("funding_source", [])

        # Add object_type to funding_source (List[FundingSource])
        for i, funding in enumerate(funding_source):
            funding_source[i]["object_type"] = "Funding source"

        # Upgrade "fundee" field to Person objects
        for i, funding in enumerate(funding_source):
            if isinstance(funding["fundee"], str):
                if "," in funding["fundee"]:
                    # Handle records where multiple fundees were put into one single string
                    fundees = funding["fundee"].split(",")
                    funding["fundee"] = [Person(name=fundee.strip()).model_dump() for fundee in fundees]
                else:
                    funding["fundee"] = [
                        Person(
                            name=funding["fundee"],
                        ).model_dump()
                    ]
            funding_source[i] = funding

        # Update "funder" field to Organization objects
        for i, funding in enumerate(funding_source):
            if isinstance(funding["funder"], str):
                if "," in funding["funder"]:
                    # Handle records where multiple funders were put into one single string
                    funders = funding["funder"].split(",")
                    # We can only keep one funder
                    funding["funder"] = Organization.from_name(funders[0].strip())
                else:
                    funding["funder"] = Organization.from_name(funding["funder"])
            funding_source[i] = funding

        if len(funding_source) == 0 and FAKE_MISSING_DATA:
            funding_source.append(
                Funding(
                    funder=Organization.AI,
                    fundee=[Person(name="unknown")],
                ).model_dump()
            )

        return funding_source

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
        if "creation_date" in data and "creation_time" in data:
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

    def _build_output_dict(self, data: dict, **kwargs) -> dict:
        """Build the output dictionary with all upgraded fields"""
        return {
            "schema_version": "2.0.0",
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
            "object_type": "Data description",
        }

    def upgrade(self, data: dict, schema_version: str) -> dict:
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

        # Build and return the upgraded output
        return self._build_output_dict(
            data,
            funding_source=funding_source,
            creation_time=creation_time,
            institution=institution,
            data_level=data_level,
            project_name=project_name,
            investigators=investigators,
            modalities=modalities,
        )
