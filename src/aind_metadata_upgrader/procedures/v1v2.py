"""<=v1.4 to v2.0 procedures upgrade functions"""

import copy
from datetime import date
from typing import Optional

from aind_data_schema.components.coordinates import CoordinateSystemLibrary
from aind_data_schema.components.surgery_procedures import (
    GenericSurgeryProcedure,
)
from aind_data_schema.core.procedures import (
    SpecimenProcedure,
    Surgery,
)

from aind_metadata_upgrader.base import CoreUpgrader
from aind_metadata_upgrader.procedures.v1v2_injections import (
    upgrade_icm_injection,
    upgrade_icv_injection,
    upgrade_intraperitoneal_injection,
    upgrade_iontophoresis_injection,
    upgrade_nanoject_injection,
    upgrade_retro_orbital_injection,
)
from aind_metadata_upgrader.procedures.v1v2_procedures import (
    repair_generic_surgery_procedure,
    upgrade_anaesthetic,
    upgrade_antibody,
    upgrade_catheter_implant,
    upgrade_craniotomy,
    upgrade_fiber_implant,
    upgrade_hcr_series,
    upgrade_headframe,
    upgrade_myomatrix_insertion,
    upgrade_other_subject_procedure,
    upgrade_perfusion,
    upgrade_planar_sectioning,
    upgrade_protective_material_replacement,
    upgrade_sample_collection,
    upgrade_water_restriction,
    upgrade_training_protocol,
    upgrade_generic_subject_procedure,
)
from aind_metadata_upgrader.utils.v1v2_utils import remove, upgrade_reagent

PROC_UPGRADE_MAP = {
    "Craniotomy": upgrade_craniotomy,
    "Headframe": upgrade_headframe,
    "Ground wire": upgrade_protective_material_replacement,
    "Nanoject injection": upgrade_nanoject_injection,
    "Iontophoresis injection": upgrade_iontophoresis_injection,
    "ICV injection": upgrade_icv_injection,
    "ICM injection": upgrade_icm_injection,
    "Retro-orbital injection": upgrade_retro_orbital_injection,
    "Intraperitoneal injection": upgrade_intraperitoneal_injection,
    "Sample collection": upgrade_sample_collection,
    "Perfusion": upgrade_perfusion,
    "Fiber implant": upgrade_fiber_implant,
    "Myomatrix_Insertion": upgrade_myomatrix_insertion,
    "Catheter implant": upgrade_catheter_implant,
    "Other Subject Procedure": upgrade_other_subject_procedure,
}


class ProceduresUpgraderV1V2(CoreUpgrader):
    """Upgrade procedures from v1.4 to v2.0"""

    def _is_old_separated_format(self, data: dict) -> bool:
        """Check if data is in the old format with separated procedure arrays"""
        has_separated_arrays = any(key in data for key in ["craniotomies", "headframes", "injections"])
        has_new_format = "subject_procedures" in data or "specimen_procedures" in data
        return has_separated_arrays and not has_new_format

    def _normalize_injection_materials(self, materials: list) -> None:
        """Normalize injection materials in place"""
        for material in materials:
            if "material_type" not in material:
                material["material_type"] = "Virus"
            # Map full_genome_name to name field for ViralMaterial
            if "full_genome_name" in material:
                material["name"] = material["full_genome_name"]
                del material["full_genome_name"]
            # Remove deprecated prep_type field
            if "prep_type" in material:
                del material["prep_type"]

    def _convert_craniotomy_procedure(self, converted: dict, old_type: str) -> None:
        """Convert craniotomy-specific fields"""
        converted["procedure_type"] = "Craniotomy"
        if old_type:
            converted["craniotomy_type"] = old_type
        # Add missing fields with defaults if not present
        if "craniotomy_coordinates_unit" not in converted:
            converted["craniotomy_coordinates_unit"] = "millimeter"
        if "craniotomy_coordinates_reference" not in converted:
            converted["craniotomy_coordinates_reference"] = "Bregma"
        if "craniotomy_size_unit" not in converted:
            converted["craniotomy_size_unit"] = "millimeter"

    def _convert_headframe_procedure(self, converted: dict, old_type: str) -> None:
        """Convert headframe-specific fields"""
        converted["procedure_type"] = "Headframe"
        if old_type:
            converted["headframe_type"] = old_type

    def _convert_injection_procedure(self, converted: dict) -> None:
        """Convert injection-specific fields"""
        # Normalize fields that should be lists
        if "injection_volume" in converted and not isinstance(converted["injection_volume"], list):
            converted["injection_volume"] = [converted["injection_volume"]]
        if "injection_coordinate_depth" in converted and not isinstance(converted["injection_coordinate_depth"], list):
            converted["injection_coordinate_depth"] = [converted["injection_coordinate_depth"]]

        # Normalize unit fields
        if converted.get("injection_angle_unit") == "degree":
            converted["injection_angle_unit"] = "degrees"

        # Normalize injection materials
        if "injection_materials" in converted and isinstance(converted["injection_materials"], list):
            self._normalize_injection_materials(converted["injection_materials"])

        # Map injection_type to procedure_type
        injection_type = converted.get("injection_type", "")
        injection_type_map = {
            "Nanoject": "Nanoject injection",
            "Iontophoresis": "Iontophoresis injection",
            "ICV": "ICV injection",
            "ICM": "ICM injection",
            "Retro-orbital": "Retro-orbital injection",
            "Intraperitoneal": "Intraperitoneal injection",
        }
        converted["procedure_type"] = injection_type_map.get(injection_type, "Nanoject injection")

    def _convert_old_procedure_to_intermediate(self, procedure: dict, array_type: str) -> dict:
        """Convert a procedure from the old separated format to intermediate format"""
        # Make a deep copy of the procedure data to avoid modifying nested structures
        converted = copy.deepcopy(procedure)

        # Handle the 'type' field from old format
        old_type = procedure.get("type", "")

        # Map array type to procedure_type and convert type field to appropriate field name
        if array_type == "craniotomies":
            self._convert_craniotomy_procedure(converted, old_type)
        elif array_type == "headframes":
            self._convert_headframe_procedure(converted, old_type)
        elif array_type == "injections":
            self._convert_injection_procedure(converted)

        # Remove the 'type' field if it exists (from old format)
        if "type" in converted:
            del converted["type"]

        return converted

    def _group_procedures_by_date(self, procedures: list) -> dict:
        """Group procedures by their start_date and end_date into surgeries"""
        # Group procedures by (start_date, end_date) tuple
        surgery_groups = {}

        for proc in procedures:
            start_date = proc.get("start_date")
            end_date = proc.get("end_date")
            key = (start_date, end_date)

            if key not in surgery_groups:
                surgery_groups[key] = []
            surgery_groups[key].append(proc)

        # Convert groups into Surgery objects
        surgeries = []
        for (start_date, end_date), procs in surgery_groups.items():
            # Use common fields from first procedure
            first_proc = procs[0]

            surgery_data = {
                "procedure_type": "Surgery",
                "start_date": start_date,
                "end_date": end_date,
                "experimenter_full_name": first_proc.get("experimenter_full_name"),
                "iacuc_protocol": first_proc.get("iacuc_protocol"),
                "protocol_id": first_proc.get("protocol_id"),
                "anaesthesia": first_proc.get("anaesthesia"),
                "procedures": procs,
            }

            surgeries.append(surgery_data)

        return surgeries

    def _convert_old_format_to_subject_procedures(self, data: dict) -> list:
        """Convert old separated format to subject_procedures format"""
        all_procedures = []

        # Process each array type
        for array_type in ["craniotomies", "headframes", "injections"]:
            if array_type in data and data[array_type]:
                for proc in data[array_type]:
                    converted = self._convert_old_procedure_to_intermediate(proc, array_type)
                    all_procedures.append(converted)

        # Group procedures by date into surgeries
        surgeries = self._group_procedures_by_date(all_procedures)

        return surgeries

    def _upgrade_subject_procedures_block(self, procedures_data: dict, v2_procedures: dict) -> None:
        """Upgrade all subject procedures from procedures_data and populate v2_procedures"""
        if "subject_procedures" in procedures_data and procedures_data["subject_procedures"]:
            for subj_proc in procedures_data["subject_procedures"]:
                upgraded_proc = self._upgrade_subject_procedure(subj_proc)
                if upgraded_proc:
                    if isinstance(upgraded_proc, list):
                        v2_procedures["subject_procedures"].extend(upgraded_proc)
                    else:
                        v2_procedures["subject_procedures"].append(upgraded_proc)

    def _upgrade_specimen_procedures_block(self, procedures_data: dict, v2_procedures: dict) -> None:
        """Upgrade all specimen procedures from procedures_data and populate v2_procedures"""
        if "specimen_procedures" in procedures_data and procedures_data["specimen_procedures"]:
            for spec_proc in procedures_data["specimen_procedures"]:
                upgraded_proc = self._upgrade_specimen_procedure(spec_proc)
                if upgraded_proc:
                    v2_procedures["specimen_procedures"].append(upgraded_proc)

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:
        """Upgrade the procedures to v2.0"""

        # Extract the nested procedures dict if it exists
        if "procedures" in data:
            procedures_data = data["procedures"]
        else:
            procedures_data = data

        self.subject_id = procedures_data.get("subject_id")

        # Check if we have the old separated format and convert it
        if self._is_old_separated_format(procedures_data):
            subject_procedures = self._convert_old_format_to_subject_procedures(procedures_data)
            procedures_data["subject_procedures"] = subject_procedures

        # Create the V2 structure
        v2_procedures = {
            "schema_version": schema_version,
            "subject_id": procedures_data.get("subject_id"),
            "subject_procedures": [],
            "specimen_procedures": [],
            "notes": procedures_data.get("notes"),
        }

        # Upgrade subject and specimen procedures
        self._upgrade_subject_procedures_block(procedures_data, v2_procedures)
        self._upgrade_specimen_procedures_block(procedures_data, v2_procedures)

        # Add coordinate system if required
        v2_procedures["coordinate_system"] = CoordinateSystemLibrary.BREGMA_ARID.model_dump()

        return v2_procedures

    def _replace_experimenter_full_name(self, data: dict):
        """Replace experimenter_full_name with experimenters list"""
        if "experimenter_full_name" in data:
            data["experimenters"] = [data["experimenter_full_name"]]
            del data["experimenter_full_name"]
        return data

    def _upgrade_procedure(self, data: dict) -> dict:
        """Use the procedure_type field and upgrade the procedure accordingly"""

        data = repair_generic_surgery_procedure(data, self.subject_id)

        procedure_type = data.get("procedure_type")

        # Remove surgery-level fields that shouldn't be in individual procedures
        # These are handled at the Surgery level
        surgery_level_fields = [
            "iacuc_protocol",
            "ethics_review_id",
            "start_date",
            "end_date",
            "experimenter_full_name",
            "anaesthesia",
            "protocol_id",
        ]
        for field in surgery_level_fields:
            remove(data, field)

        # Map V1 procedure types to their upgrade functions

        if procedure_type in PROC_UPGRADE_MAP:
            return PROC_UPGRADE_MAP[procedure_type](data)
        else:
            raise ValueError(f"Unsupported procedure type: {procedure_type}")

    def _process_surgery_procedures(self, data: dict) -> None:
        """Process procedures for surgery upgrade"""
        procedures = data.get("procedures", [])
        data["procedures"] = []

        for procedure in procedures:
            upgraded = self._upgrade_procedure(procedure)
            if isinstance(upgraded, tuple):
                upgraded, measured_coordinates = upgraded
                if measured_coordinates:
                    if "measured_coordinates" not in data:
                        data["measured_coordinates"] = []
                    data["measured_coordinates"].extend(measured_coordinates)

            if isinstance(upgraded, list):
                data["procedures"].extend(upgraded)
            else:
                data["procedures"].append(upgraded)

        # Add default procedure if none provided
        if len(procedures) == 0:
            data["procedures"].append(
                GenericSurgeryProcedure(
                    description="(v1v2 upgrader) No procedures provided for surgery",
                ).model_dump()
            )

    def _finalize_surgery_data(self, data: dict) -> dict:
        """Finalize surgery data and create Surgery object"""
        # Handle anaesthesia
        if "anaesthesia" in data and data["anaesthesia"]:
            data["anaesthesia"] = upgrade_anaesthetic(data.get("anaesthesia", {}))

        # Set default start_date if missing
        if "start_date" not in data or not data["start_date"]:
            data["start_date"] = date(1970, 1, 1)

        # Remove end_date - Surgery doesn't have this field
        remove(data, "end_date")

        # Replace list of measured_coordinate dicts with a single dictionary
        if "measured_coordinates" in data:
            coord_list = data["measured_coordinates"]
            data["measured_coordinates"] = {}
            for coord in coord_list:
                data["measured_coordinates"].update(coord)

        surgery = Surgery(**data)
        return surgery.model_dump()

    def _upgrade_subject_procedure(self, data: dict):
        """Upgrade a single subject procedure from V1 to V2"""
        procedure_type = data.get("procedure_type")

        if procedure_type == "Surgery":
            remove(data, "procedure_type")  # Remove procedure_type as it's not needed in V2
            data = self._replace_experimenter_full_name(data)
            data["ethics_review_id"] = data.get("iacuc_protocol", None)
            remove(data, "iacuc_protocol")

            self._process_surgery_procedures(data)
            return self._finalize_surgery_data(data)

        elif procedure_type == "Water restriction":
            return upgrade_water_restriction(data)
        elif procedure_type == "Training protocol":
            return upgrade_training_protocol(data)
        elif procedure_type == "Generic Subject Procedure":
            # Convert experimenter_full_name to experimenters list
            data = self._replace_experimenter_full_name(data)
            return upgrade_generic_subject_procedure(data)

        raise ValueError("Unsupported subject procedure type: {}".format(procedure_type))

    def _upgrade_specimen_procedure(self, data: dict) -> dict:
        """Upgrade a single specimen procedure from V1 to V2"""
        procedure_type = data.get("procedure_type")

        # Convert experimenter_full_name to experimenters list
        experimenters = []
        if data.get("experimenter_full_name"):
            experimenters.append(data["experimenter_full_name"])

        # Convert protocol_id from list to string (V1 has it as list, V2 as string)
        protocol_id = data.get("protocol_id", None)
        if isinstance(protocol_id, str) and protocol_id.lower() == "none":
            protocol_id = None
        if not isinstance(protocol_id, list):
            protocol_id = [protocol_id] if protocol_id else []

        # Create procedure_details from reagents, antibodies, hcr_series, sectioning
        procedure_details = []

        reagents = data.get("reagents", [])
        reagents = [upgrade_reagent(r) for r in reagents]

        procedure_details.extend(reagents)

        if data.get("antibodies") and isinstance(data["antibodies"], list):
            antibodies = [upgrade_antibody(ab) for ab in data["antibodies"]]
            procedure_details.extend(antibodies)
        if data.get("hcr_series") and data["hcr_series"]:
            procedure_details.append(upgrade_hcr_series(data["hcr_series"]))
        if data.get("sectioning") and data["sectioning"]:
            procedure_details.append(upgrade_planar_sectioning(data["sectioning"]))

        specimen_id = data.get("specimen_id", None)

        if "subject_id" not in specimen_id:
            specimen_id = f"{self.subject_id}_{specimen_id}"

        specimen_procedure = SpecimenProcedure(
            procedure_type=procedure_type,
            specimen_id=specimen_id,
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            experimenters=experimenters,
            protocol_id=protocol_id,
            procedure_name=data.get("procedure_name"),
            procedure_details=procedure_details,
            notes=data.get("notes"),
        )

        return specimen_procedure.model_dump()
