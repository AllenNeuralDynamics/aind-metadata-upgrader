"""<=v1.4 to v2.0 procedures upgrade functions"""

from aind_data_schema.components.identifiers import Person

from aind_metadata_upgrader.base import CoreUpgrader

from aind_data_schema.core.procedures import (
    Surgery,
)

from aind_metadata_upgrader.utils.v1v2_utils import remove
from aind_metadata_upgrader.procedures.v1v2_procedures import (
    upgrade_craniotomy,
    upgrade_headframe,
    upgrade_protective_material_replacement,
    upgrade_nanoject_injection,
    upgrade_iontophoresis_injection,
    upgrade_icv_injection,
    upgrade_icm_injection,
    upgrade_retro_orbital_injection,
    upgrade_intraperitoneal_injection,
    upgrade_sample_collection,
    upgrade_perfusion,
    upgrade_fiber_implant,
    upgrade_myomatrix_insertion,
    upgrade_catheter_implant,
    upgrade_other_subject_procedure,
)


class ProceduresUpgraderV1V2(CoreUpgrader):
    """Upgrade procedures from v1.4 to v2.0"""

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the procedures to v2.0"""
        # Extract the nested procedures dict if it exists
        if "procedures" in data:
            procedures_data = data["procedures"]
        else:
            procedures_data = data

        # Create the V2 structure
        v2_procedures = {
            "schema_version": schema_version,
            "subject_id": procedures_data.get("subject_id"),
            "subject_procedures": [],
            "specimen_procedures": [],
            "implanted_devices": [],
            "configurations": [],
            "coordinate_system": None,
            "notes": procedures_data.get("notes"),
        }

        # Upgrade subject procedures
        if "subject_procedures" in procedures_data:
            for subj_proc in procedures_data["subject_procedures"]:
                upgraded_proc = self._upgrade_subject_procedure(subj_proc)
                if upgraded_proc:
                    v2_procedures["subject_procedures"].append(upgraded_proc)

        # Upgrade specimen procedures
        if "specimen_procedures" in procedures_data:
            for spec_proc in procedures_data["specimen_procedures"]:
                upgraded_proc = self._upgrade_specimen_procedure(spec_proc)
                if upgraded_proc:
                    v2_procedures["specimen_procedures"].append(upgraded_proc)

        return v2_procedures
    
    def _replace_experimenter_full_name(self, data: dict):
        """Replace experimenter_full_name with experimenters list"""
        if "experimenter_full_name" in data:
            experimenter = Person(name=data["experimenter_full_name"])
            data["experimenters"] = [experimenter]
            del data["experimenter_full_name"]
        return data
    
    def _upgrade_procedure(self, data: dict) -> dict:
        """Use the procedure_type field and upgrade the procedure accordingly"""

        procedure_type = data.get("procedure_type")

        # Map V1 procedure types to their upgrade functions
        upgrade_map = {
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

        if procedure_type in upgrade_map:
            return upgrade_map[procedure_type](data)
        else:
            raise ValueError(f"Unsupported procedure type: {procedure_type}")

    def _upgrade_subject_procedure(self, data: dict):
        """Upgrade a single subject procedure from V1 to V2"""
        # V1 has Surgery as subject procedure type, V2 uses Surgery directly
        if data.get("procedure_type") == "Surgery":
            remove(data, "procedure_type")  # Remove procedure_type as it's not needed in V2

            data = self._replace_experimenter_full_name(data)

            data["ethics_review_id"] = data.get("iacuc_protocol", None)
            remove(data, "iacuc_protocol")

            procedures = data.get("procedures", [])
            data["procedures"] = [self._upgrade_procedure(proc) for proc in procedures]

            surgery = Surgery(
                **data,
            )
            return surgery.model_dump()

        print(data)
        raise ValueError("Unsupported subject procedure type: {}".format(data.get("procedure_type")))

    def _upgrade_specimen_procedure(self, spec_proc: dict) -> dict:
        """Upgrade a single specimen procedure from V1 to V2"""
        procedure_type = spec_proc.get("procedure_type")

        # Convert experimenter_full_name to experimenters list
        experimenters = []
        if spec_proc.get("experimenter_full_name"):
            experimenter = Person(name=spec_proc["experimenter_full_name"])
            experimenters.append(experimenter)

        # Convert protocol_id from list to string (V1 has it as list, V2 as string)
        protocol_id = spec_proc.get("protocol_id", ["unknown"])
        if isinstance(protocol_id, list):
            protocol_id = protocol_id[0] if protocol_id else "unknown"

        # Create procedure_details from reagents, antibodies, hcr_series, sectioning
        procedure_details = {}
        if spec_proc.get("reagents"):
            procedure_details["reagents"] = spec_proc["reagents"]
        if spec_proc.get("antibodies"):
            procedure_details["antibodies"] = spec_proc["antibodies"]
        if spec_proc.get("hcr_series"):
            procedure_details["hcr_series"] = spec_proc["hcr_series"]
        if spec_proc.get("sectioning"):
            procedure_details["sectioning"] = spec_proc["sectioning"]

        return {
            "procedure_type": procedure_type,
            "specimen_id": spec_proc.get("specimen_id"),
            "start_date": spec_proc.get("start_date"),
            "end_date": spec_proc.get("end_date"),
            "experimenters": experimenters,
            "protocol_id": protocol_id,
            "procedure_name": spec_proc.get("procedure_name"),
            "procedure_details": procedure_details if procedure_details else None,
            "notes": spec_proc.get("notes"),
        }
