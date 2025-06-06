"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_data_schema.components.identifiers import Person
from aind_data_schema.core.data_description import Funding
from aind_data_schema_models.licenses import License
from aind_data_schema_models.organizations import Organization

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.settings import FAKE_MISSING_DATA
from aind_metadata_upgrader.utils.v1v2_utils import upgrade_v1_modalities

DATA_LEVEL_MAP = {
    "raw data": "raw",
}


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
                    funding["fundee"] = [Person(name=fundee.strip()) for fundee in fundees]
                else:
                    funding["fundee"] = Person(
                        name=funding["fundee"],
                    )
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

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the data description to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # removed fields:
        # platform
        # label
        # related_data

        # remaining fields:
        schema_version = "2.0.0"
        license = data.get("license", License.CC_BY_40)
        subject_id = data.get("subject_id", None)

        # Handle old records that have both creation_date and creation_time
        if "creation_date" in data and "creation_time" in data:
            creation_time = data["creation_date"] + "T" + data["creation_time"]
        else:
            creation_time = data.get("creation_time", None)
        tags = data.get("tags", None)
        name = data.get("name", None)

        # Handle old records that have institution as a string
        institution = data.get("institution", None)
        if isinstance(institution, str):
            try:
                institution = Organization.from_abbreviation(institution)
            except ValueError:
                raise ValueError(f"Unsupported institution abbreviation: {institution}")

        funding_source = self._get_funding_source(data)

        # Handle old data_level types
        data_level = data.get("data_level", None)
        if data_level and data_level in DATA_LEVEL_MAP.keys():
            data_level = DATA_LEVEL_MAP[data_level]

        group = data.get("group", None)

        # Originally a List[PIDName], now List[Person]
        investigators = self._get_investigators(data)

        if len(investigators) == 0:
            # Create a fake investigator
            investigators.append(Person(name="unknown"))

        # Handle missing project_name
        project_name = data.get("project_name", "unknown")
        if not project_name:
            project_name = "unknown"

        restrictions = data.get("restrictions", None)

        # Modalities may need to be converted to a list
        modalities = upgrade_v1_modalities(data)

        # New fields
        data_summary = data.get("data_summary", None)
        object_type = "Data description"
        tags = None

        output = {
            # new fields in v2
            "schema_version": schema_version,
            "license": license,
            "subject_id": subject_id,
            "creation_time": creation_time,
            "tags": tags,
            "name": name,
            "institution": institution,
            "funding_source": funding_source,
            "data_level": data_level,
            "group": group,
            "investigators": investigators,
            "project_name": project_name,
            "restrictions": restrictions,
            "modalities": modalities,
            "data_summary": data_summary,
            "object_type": object_type,
            "tags": tags,
        }

        return output
