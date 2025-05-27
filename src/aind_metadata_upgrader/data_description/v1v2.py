"""<=v1.4 to v2.0 data description upgrade functions"""

from aind_metadata_upgrader.base import CoreUpgrader
from aind_data_schema_models.licenses import License
from aind_data_schema.components.identifiers import Person


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
        schema_version = schema_version
        license = data.get("license", License.CC_BY_40)
        subject_id = data.get("subject_id", None)
        creation_time = data.get("creation_time", None)
        tags = data.get("tags", None)
        name = data.get("name", None)
        institution = data.get("institution", None)

        funding_source = data.get("funding_source", [])
        # Add object_type to funding_source (List[FundingSource])
        for i, funding in enumerate(funding_source):
            funding["object_type"] = "Funding source"
            if isinstance(funding["fundee"], str):
                funding["fundee"] = Person(
                    name=funding["fundee"],
                )
            funding_source[i] = funding

        data_level = data.get("data_level", None)
        group = data.get("group", None)

        # Originally a List[PIDName], now List[Person]
        investigators = data.get("investigators", [])
        for i, investigator in enumerate(investigators):
            # Convert from PIDName to Person 
            if not isinstance(investigator, Person):
                investigators[i] = Person(
                    name=investigator["name"],
                )

        # Handle missing project_name
        project_name = data.get("project_name", "unknown")
        if not project_name:
            project_name = "unknown"

        restrictions = data.get("restrictions", None)

        # Modalities may need to be converted to a list
        modalities = data.get("modality", [])
        if not isinstance(modalities, list):
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
