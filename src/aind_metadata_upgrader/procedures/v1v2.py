"""<=v1.4 to v2.0 procedures upgrade functions"""

from aind_data_schema.components.identifiers import Person

from aind_metadata_upgrader.base import CoreUpgrader

from aind_data_schema.core.procedures import (
    Surgery,
    SpecimenProcedure,
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
    upgrade_reagent,
    upgrade_anaesthetic,
)

from aind_data_schema.components.coordinates import CoordinateSystemLibrary


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
            print(data)
            remove(data, "procedure_type")  # Remove procedure_type as it's not needed in V2

            data = self._replace_experimenter_full_name(data)

            data["ethics_review_id"] = data.get("iacuc_protocol", None)
            remove(data, "iacuc_protocol")

            procedures = data.get("procedures", [])
            data["procedures"] = [self._upgrade_procedure(proc) for proc in procedures]

            if len(procedures) == 0:
                print(data)
                raise ValueError("Surgery must have at least one procedure")

            if "anaesthesia" in data and data["anaesthesia"]:
                data["anaesthesia"] = upgrade_anaesthetic(data.get("anaesthesia", {}))

            surgery = Surgery(
                **data,
            )
            return surgery.model_dump()

        print(data)
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

        if data.get("antibodies"):
            procedure_details.append(data["antibodies"])
        if data.get("hcr_series"):
            procedure_details.append(data["hcr_series"])
        if data.get("sectioning"):
            procedure_details.append(data["sectioning"])

        specimen_procedure = SpecimenProcedure(
            procedure_type=procedure_type,
            specimen_id=data.get("specimen_id"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            experimenters=experimenters,
            protocol_id=protocol_id,
            procedure_name=data.get("procedure_name"),
            procedure_details=procedure_details,
            notes=data.get("notes"),
        )

        return specimen_procedure.model_dump()
