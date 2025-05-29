"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader
from aind_data_schema_models.licenses import License
from aind_data_schema.components.identifiers import Person

from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.modalities import Modality

DATA_LEVEL_MAP = {
    "raw data": "raw",
}


class DataDescriptionV1V2(CoreUpgrader):
    """Upgrade data description from v1.4 to v2.0"""

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

        funding_source = data.get("funding_source", [])
        # Add object_type to funding_source (List[FundingSource])
        for i, funding in enumerate(funding_source):
            funding["object_type"] = "Funding source"
            if isinstance(funding["fundee"], str):
                funding["fundee"] = Person(
                    name=funding["fundee"],
                )
            funding_source[i] = funding

        # Handle old data_level types
        data_level = data.get("data_level", None)
        if data_level and data_level in DATA_LEVEL_MAP.keys():
            data_level = DATA_LEVEL_MAP[data_level]

        group = data.get("group", None)

        # Originally a List[PIDName], now List[Person]
        investigators = data.get("investigators", [])
        for i, investigator in enumerate(investigators):
            # Convert from PIDName to Person
            if not isinstance(investigator, Person):
                investigators[i] = Person(
                    name=investigator["name"],
                )

        if len(investigators) == 0:
            # Create a fake investigator
            investigators.append(Person(name="unknown"))

        # Handle missing project_name
        project_name = data.get("project_name", "unknown")
        if not project_name:
            project_name = "unknown"

        restrictions = data.get("restrictions", None)

        # Modalities may need to be converted to a list
        modalities = data.get("modality", [])
        if not isinstance(modalities, list):
            if isinstance(modalities, str):
                # Coerce single modality to it's object

            modalities = [modalities]

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
