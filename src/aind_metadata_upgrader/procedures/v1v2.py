"""<=v1.4 to v2.0 procedures upgrade functions"""

from datetime import date

from aind_data_schema.components.identifiers import Person

from aind_metadata_upgrader.base import CoreUpgrader

from aind_data_schema.core.procedures import (
    Surgery,
    WaterRestriction,
    TrainingProtocol,
    GenericSubjectProcedure,
    SpecimenProcedure,
)
from aind_data_schema.components.surgery_procedures import GenericSurgeryProcedure


from aind_metadata_upgrader.utils.v1v2_utils import remove
from aind_metadata_upgrader.procedures.v1v2_procedures import (
    upgrade_craniotomy,
    upgrade_headframe,
    upgrade_protective_material_replacement,
    upgrade_sample_collection,
    upgrade_perfusion,
    upgrade_fiber_implant,
    upgrade_myomatrix_insertion,
    upgrade_catheter_implant,
    upgrade_other_subject_procedure,
    upgrade_reagent,
    upgrade_anaesthetic,
    repair_generic_surgery_procedure,
    upgrade_antibody,
    upgrade_hcr_series,
    upgrade_planar_sectioning,
)
from aind_metadata_upgrader.procedures.v1v2_injections import (
    upgrade_nanoject_injection,
    upgrade_iontophoresis_injection,
    upgrade_icv_injection,
    upgrade_icm_injection,
    upgrade_retro_orbital_injection,
    upgrade_intraperitoneal_injection,
)

from aind_data_schema.components.coordinates import CoordinateSystemLibrary

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

    def upgrade(self, data: dict, schema_version: str) -> dict:
        """Upgrade the procedures to v2.0"""

        # Extract the nested procedures dict if it exists
        if "procedures" in data:
            procedures_data = data["procedures"]
        else:
            procedures_data = data

        self.subject_id = procedures_data.get("subject_id")

        # Create the V2 structure
        v2_procedures = {
            "schema_version": schema_version,
            "subject_id": procedures_data.get("subject_id"),
            "subject_procedures": [],
            "specimen_procedures": [],
            "notes": procedures_data.get("notes"),
        }

        # Upgrade subject procedures
        if "subject_procedures" in procedures_data:
            for subj_proc in procedures_data["subject_procedures"]:
                upgraded_proc = self._upgrade_subject_procedure(subj_proc)
                if upgraded_proc:
                    if isinstance(upgraded_proc, list):
                        v2_procedures["subject_procedures"].extend(upgraded_proc)
                    else:
                        v2_procedures["subject_procedures"].append(upgraded_proc)

        # Upgrade specimen procedures
        if "specimen_procedures" in procedures_data:
            for spec_proc in procedures_data["specimen_procedures"]:
                upgraded_proc = self._upgrade_specimen_procedure(spec_proc)
                if upgraded_proc:
                    v2_procedures["specimen_procedures"].append(upgraded_proc)

        # Add coordinate system if required
        v2_procedures["coordinate_system"] = CoordinateSystemLibrary.BREGMA_ARID.model_dump()

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

        data = repair_generic_surgery_procedure(data, self.subject_id)

        procedure_type = data.get("procedure_type")

        if "iacuc_protocol" in data:
            # Replace iacuc_protocol with ethics_review_id
            data["ethics_review_id"] = data.get("iacuc_protocol", None)
            remove(data, "iacuc_protocol")

        # Map V1 procedure types to their upgrade functions

        if procedure_type in PROC_UPGRADE_MAP:
            return PROC_UPGRADE_MAP[procedure_type](data)
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
            data["procedures"] = []
            for procedure in procedures:
                upgraded = self._upgrade_procedure(procedure)
                if isinstance(upgraded, list):
                    data["procedures"].extend(upgraded)
                else:
                    data["procedures"].append(upgraded)

            if len(procedures) == 0:
                data["procedures"].append(
                    GenericSurgeryProcedure(
                        description="(v1v2 upgrader) No procedures provided for surgery",
                    ).model_dump()
                )

            if "anaesthesia" in data and data["anaesthesia"]:
                data["anaesthesia"] = upgrade_anaesthetic(data.get("anaesthesia", {}))

            if "start_date" not in data or not data["start_date"]:
                # If start_date is not provided, set it to today's date
                data["start_date"] = date(1970, 1, 1)

            surgery = Surgery(
                **data,
            )
            return surgery.model_dump()
        elif data.get("procedure_type") == "Water restriction":
            remove(data, "procedure_type")
            data["ethics_review_id"] = data.get("iacuc_protocol", "unknown")
            remove(data, "iacuc_protocol")
            return WaterRestriction(
                **data,
            ).model_dump()
        elif data.get("procedure_type") == "Training protocol":
            remove(data, "procedure_type")
            data["ethics_review_id"] = data.get("iacuc_protocol", "unknown")
            remove(data, "iacuc_protocol")
            return TrainingProtocol(
                **data,
            ).model_dump()
        elif data.get("procedure_type") == "Generic Subject Procedure":
            # Convert experimenter_full_name to experimenters list
            data = self._replace_experimenter_full_name(data)

            # Convert protocol_id from list to string (V1 has it as list, V2 as string)
            protocol_id = data.get("protocol_id", None)
            if isinstance(protocol_id, str) and protocol_id.lower() == "none":
                protocol_id = None

            generic_subject_procedure = GenericSubjectProcedure(
                start_date=data.get("start_date"),
                experimenters=data.get("experimenters", []),
                ethics_review_id=data.get("iacuc_protocol", "unknown"),
                protocol_id=protocol_id,
                description=data.get("description", ""),
                notes=data.get("notes"),
            )

            return generic_subject_procedure.model_dump()

        raise ValueError("Unsupported subject procedure type: {}".format(data.get("procedure_type")))

    def _upgrade_specimen_procedure(self, data: dict) -> dict:
        """Upgrade a single specimen procedure from V1 to V2"""
        procedure_type = data.get("procedure_type")

        # Convert experimenter_full_name to experimenters list
        experimenters = []
        if data.get("experimenter_full_name"):
            experimenter = Person(name=data["experimenter_full_name"])
            experimenters.append(experimenter)

        # Convert protocol_id from list to string (V1 has it as list, V2 as string)
        protocol_id = data.get("protocol_id", None)
        if isinstance(protocol_id, str) and protocol_id.lower() == "none":
            protocol_id = None

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
