"""Module to contain code to uprgade old procedures"""
from typing import Any, Optional, Union

import semver

from aind_data_schema.base import AindModel
from aind_metadata_upgrader.base_upgrade import BaseModelUpgrade


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
    ViralMaterial,
    NonViralMaterial
)

import logging


def pop_unused_fields(instance: dict, model):
    remove_fields = []

    for field in instance.keys():
        if field not in model.model_fields.keys():
            remove_fields.append(field)

    for field in remove_fields:
        instance.pop(field)

    return instance


class InjectionMaterialsUpgrade:

    @staticmethod
    def upgrade_injection_materials(old_injection_materials: list) -> Optional[dict]:
        """Map legacy InjectionMaterials model to current version"""

        new_materials = []
        for injection_material in old_injection_materials: #this wont work like i want, we changed the naming convention
            new_material = None

            print("injection material: ", injection_material)
            if injection_material.get("titer") is not None:

                injection_material = pop_unused_fields(injection_material, ViralMaterial)
                
                new_material = ViralMaterial.model_construct(injection_material)
            elif injection_material.get("concentration") is not None:

                injection_material = pop_unused_fields(injection_material, NonViralMaterial)

                new_material = NonViralMaterial.model_construct(injection_material)
            else:
                logging.error(f"Injection material with no titer or concentration {injection_material} passed in")

            if new_material:
                new_materials.append(new_material)
        
        return new_materials
                

                

        


class ProcedureUpgrade(BaseModelUpgrade):
    """Handle upgrades for Procedure models."""

    procedure_types_list = {
        model.model_fields["procedure_type"].default: model for model in [
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

        print("subj procedure to upgrade: ", len(old_subj_procedure.keys()), old_subj_procedure.keys())

        procedure_type = old_subj_procedure.get("procedure_type")
        if procedure_type in self.procedure_types_list.keys():
            remove_fields = []
            for field in old_subj_procedure.keys():
                if field not in self.procedure_types_list[procedure_type].model_fields.keys():
                    remove_fields.append(field)

            for field in remove_fields:
                old_subj_procedure.pop(field)

            print("before validation: ", len(old_subj_procedure.keys()), old_subj_procedure.keys())

            if "injection_materials" in old_subj_procedure.keys():
                old_subj_procedure["injection_materials"] = InjectionMaterialsUpgrade.upgrade_injection_materials(old_subj_procedure["injection_materials"])

            return self.procedure_types_list[procedure_type].model_validate(old_subj_procedure)
        else:
            logging.error(f"Procedure type {procedure_type} not found in list of procedure types")
            return None
        
    @staticmethod
    def upgrade_specimen_procedure(old_specimen_procedure: Any) -> Optional[SpecimenProcedure]:
        """Map legacy SpecimenProcedure model to current version"""

        if type(old_specimen_procedure) is SpecimenProcedure:
            return old_specimen_procedure
        elif type(old_specimen_procedure) is dict and old_specimen_procedure.procedure_type is not None:
            return SpecimenProcedure.model_validate(old_specimen_procedure)
        else:
            logging.error(f"Specimen procedure {old_specimen_procedure} passed in as invalid type")
            return None

    def upgrade_procedure(self) -> Optional[Procedures]:
        """Map legacy Procedure model to current version"""

        
        print("from init: ", self.old_model)
        print(self.old_model.schema_version)

        if semver.Version.parse(self.old_model.schema_version) <= semver.Version.parse("0.11.0"):
            subj_id = self.old_model.subject_id

            loaded_subject_procedures = {}
            for subj_procedure in self.old_model.subject_procedures: #type: dict
                date = subj_procedure.get("start_date")

                logging.info(f"Upgrading procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}")

                print("full name: ", subj_procedure.get("experimenter_full_name"))

                upgraded_subj_procedure = self.upgrade_subject_procedure(old_subj_procedure=subj_procedure)
                
                if not upgraded_subj_procedure:
                    continue
                

                if date not in loaded_subject_procedures.keys():
                    new_surgery = Surgery(
                        start_date=date,
                        experimenter_full_name=str(subj_procedure.get("experimenter_full_name")),
                        iacuc_protocol=subj_procedure.get("iacuc_protocol"),
                        animal_weight_prior=subj_procedure.get("animal_weight_prior"),
                        animal_weight_post=subj_procedure.get("animal_weight_post"),
                        weight_unit=subj_procedure.get("weight_unit", Surgery.model_fields["weight_unit"].default),
                        anaesthesia=subj_procedure.get("anaesthesia"),
                        workstation_id=subj_procedure.get("workstation_id"),
                        procedures=[upgraded_subj_procedure],
                        notes=subj_procedure.get("notes")
                    )
                    loaded_subject_procedures = {date: new_surgery}
                else:
                    loaded_subject_procedures[date].procedures.append(upgraded_subj_procedure)
                
            loaded_spec_procedures = []
            for spec_procedure in self.old_model.specimen_procedures:
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
                notes=self.old_model.notes,
            )

            return new_procedure