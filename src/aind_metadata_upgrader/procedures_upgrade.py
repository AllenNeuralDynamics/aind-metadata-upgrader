"""Module to contain code to uprgade old procedures"""
from typing import Any, Optional, Union

import semver

from aind_data_schema.base import AindModel
from aind_data_schema.schema_upgrade.base_upgrade import BaseModelUpgrade

from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
    Craniotomy,
    FiberImplant,
    Headframe,
    IntraCerebellarVentricleInjection,
    IntraCisternalMagnaInjection,
    IntraperitonealInjection,
    IontophoresisInjection,
    NanojectInjection,
    Perfusion,
    OtherSubjectProcedure,
    RetroOrbitalInjection,
    SpecimenProcedure,
)

import logging





class ProcedureUpgrade(BaseModelUpgrade):
    """Handle upgrades for Procedure models."""

    procedure_types_list = {
        model.procedure_type: model for model in [
            Procedures, 
            Surgery,
            Craniotomy,
            FiberImplant,
            Headframe,
            IntraCerebellarVentricleInjection,
            IntraCisternalMagnaInjection,
            IntraperitonealInjection,
            IontophoresisInjection,
            NanojectInjection,
            Perfusion,
            OtherSubjectProcedure,
            RetroOrbitalInjection,
        ]
    }

    def __init__(self, old_procedures_model: Procedures):
        super().__init__(old_procedures_model, model_class=Procedures)

    
    def upgrade_subject_procedure(self, old_subj_procedure: dict):
        """Map legacy SubjectProcedure model to current version"""

        procedure_type = old_subj_procedure.get("procedure_type")
        if procedure_type in self.procedure_types_list.keys():
            return self.procedure_types_list[procedure_type].model_validate(old_subj_procedure)
        else:
            logging.error(f"Procedure type {procedure_type} not found in list of procedure types")
            return None
        
    @staticmethod
    def upgrade_specimen_procedure(old_specimen_procedure: Any) -> Optional[SpecimenProcedure]:
        """Map legacy SpecimenProcedure model to current version"""

        if type(old_specimen_procedure) is SpecimenProcedure:
            return old_specimen_procedure
        elif type(old_specimen_procedure) is dict and old_specimen_procedure.get("procedure_type") is not None:
            return SpecimenProcedure.model_validate(old_specimen_procedure)
        else:
            logging.error(f"Specimen procedure {old_specimen_procedure} passed in as invalid type")
            return None

    @staticmethod
    def upgrade_procedure(old_procedure: Any) -> Optional[Procedures]:
        """Map legacy Procedure model to current version"""

        if semver.Version.parse(old_procedure.get("schema_version")) <= semver.Version.parse("0.11.0"):
            subj_id = old_procedure.get("subject_id")

            loaded_subject_procedures = {}
            for subj_procedure in old_procedure.get("subject_procedures"): #type: dict
                date = subj_procedure.get("start_date")

                logging.info(f"Upgrading procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}")

                upgraded_subj_procedure = ProcedureUpgrade.upgrade_subject_procedure(subj_procedure)
                
                if not upgraded_subj_procedure:
                    continue
                

                if date not in loaded_subject_procedures.keys():
                    new_surgery = Surgery(
                        start_date=date,
                        experimenter_full_name=str(subj_procedure.get("experimenter_full_name")),
                        iacuc_protocol=subj_procedure.get("iacuc_protocol"),
                        animal_weight_prior=subj_procedure.get("animal_weight_prior"),
                        animal_weight_post=subj_procedure.get("animal_weight_post"),
                        weight_unit=subj_procedure.get("weight_unit"),
                        anaesthesia=subj_procedure.get("anaesthesia"),
                        workstation_id=subj_procedure.get("workstation_id"),
                        procedures=[upgraded_subj_procedure],
                        notes=subj_procedure.get("notes")
                    )
                    loaded_subject_procedures = {date: new_surgery}
                else:
                    loaded_subject_procedures[date].procedures.append(upgraded_subj_procedure)
                
            loaded_spec_procedures = []
            for spec_procedure in old_procedure.specimen_procedures:
                date = spec_procedure.start_date

                logging.info(f"Upgrading procedure {spec_procedure.get('procedure_type')} for subject {subj_id} on date {date}")

                upgraded_spec_procedure = ProcedureUpgrade.upgrade_specimen_procedure(spec_procedure)
                
                if not upgraded_spec_procedure:
                    continue
                
                loaded_spec_procedures.append(upgraded_spec_procedure)

            new_procedure = Procedures(
                subject_id=subj_id,
                subject_procedures=list(loaded_subject_procedures.values()),
                specimen_procedures=loaded_spec_procedures,
                notes=old_procedure.notes,
            )

            return new_procedure