"""<=v1.4 to v2.0 data description upgrade functions"""

from typing import Optional

from aind_data_schema.components.subjects import BreedingInfo, MouseSubject
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.species import Species, Strain

from aind_metadata_upgrader.base import CoreUpgrader

from aind_metadata_upgrader.utils.v1v2_utils import upgrade_registry


class SubjectUpgraderV1V2(CoreUpgrader):
    """Upgrade subject core file from v1.x to v2.0"""

    def _get_background_strain(self, data: dict) -> dict:
        """Handle background strain upgrade logic"""
        background_strain = data.get("background_strain", None)
        if isinstance(background_strain, str):
            if background_strain == "BALB/C":
                background_strain = Strain.BALB_C
            elif background_strain == "C57BL/6J":
                background_strain = Strain.C57BL_6J
            else:
                raise ValueError(f"Unsupported background strain: {background_strain}")
        if not background_strain:
            background_strain = Strain.C57BL_6J  # Default to C57BL/6J if not specified [TODO: FIX THIS]

        return background_strain.model_dump()

    def _get_breeding_info(self, data: dict) -> Optional[dict]:
        """Handle breeding info upgrade logic"""
        breeding_info = data.get("breeding_info", None)
        if breeding_info:
            # Ensure object_type is set
            breeding_info["object_type"] = "Breeding info"
            # Ensure all fields are strings, fill with unknown if missing
            fields = ["breeding_group", "maternal_genotype", "paternal_genotype", "maternal_id", "paternal_id"]
            for field in fields:
                if not breeding_info.get(field):
                    breeding_info[field] = "unknown"

        return breeding_info

    def _process_species_and_strain(self, data: dict):
        """Process and validate species and background strain data"""
        # Species model seems to have changed for some records, make sure it matches the new model
        species = data.get("species", None)
        if species and isinstance(species, str) and species == "Mus musculus":
            # Convert string species name to Species model
            species = Species.HOUSE_MOUSE.model_dump()
        if species and isinstance(species, dict) and species["name"] == "Mus musculus":
            # Replace with the new Species model
            species = Species.HOUSE_MOUSE.model_dump()
        else:
            raise ValueError("Species must be specified")

        if isinstance(species["registry"], dict):
            species = upgrade_registry(species)

        # Handle upgrade to new Strain
        background_strain = self._get_background_strain(data)
        if isinstance(background_strain["registry"], dict):
            background_strain = upgrade_registry(background_strain)

        return species, background_strain

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the subject core file data to v2.0"""

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # root level fields
        subject_id = data.get("subject_id")
        notes = data.get("notes", "")

        # subject details
        sex = data.get("sex", "unknown")
        date_of_birth = data.get("date_of_birth", "")
        genotype = data.get("genotype", "unknown")

        species, background_strain = self._process_species_and_strain(data)

        alleles = data.get("alleles", [])

        # Add object_type
        breeding_info = self._get_breeding_info(data)

        # If missing, assign to "Other" and update notes
        source = data.get("source", None)
        if source:
            source = upgrade_registry(source)
        if not source:
            source = Organization.OTHER
            if not notes:
                notes = ""
            notes += " (SubjectUpgraderV1V2): Source not specified, defaulting to 'Other'."

        rrid = data.get("rrid", None)
        restrictions = data.get("restrictions", None)

        # Upgrade to a list if missing
        wellness_reports = data.get("wellness_reports", [])
        if not wellness_reports:
            wellness_reports = []

        # Add object type
        housing = data.get("housing", None)
        if housing:
            housing["object_type"] = "Housing"

        # Package MouseSubject
        if species["name"] == "Mus musculus":
            mouse_subject = MouseSubject(
                sex=sex,
                date_of_birth=date_of_birth,
                strain=background_strain,
                species=species,
                alleles=alleles,
                genotype=genotype,
                breeding_info=BreedingInfo(**breeding_info) if breeding_info else None,
                wellness_reports=wellness_reports,
                housing=housing,
                source=source,
                restrictions=restrictions,
                rrid=rrid,
            )
            mouse_subject = mouse_subject.model_dump()
        else:
            raise ValueError(f"Species {species['name']} is not supported for V1->V2 upgrade")

        return {
            "object_type": "Subject",
            "subject_id": subject_id,
            "notes": notes,
            "subject_details": mouse_subject,
            "schema_version": schema_version,
        }
