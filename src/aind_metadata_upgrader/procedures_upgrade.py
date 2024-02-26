"""Module to contain code to uprgade old procedures"""
from typing import Any, Optional, Union

from aind_metadata_upgrader.utils import check_field, get_or_default, drop_unused_fields

from pydantic import ValidationError

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
    NonViralMaterial,
    OphysProbe
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


class SubjectProcedureModelsUpgrade:
    """Handle upgrades for SubjectProcedure models."""


    def upgrade_craniotomy(old_subj_procedure: dict):
        """Map legacy Craniotomy model to current version"""

        if not check_field(old_subj_procedure, "protocol_id"):
            old_subj_procedure["protocol_id"] = "unknown"

        try:
            return Craniotomy.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating IntraperitonealInjection: {e}")
            return Craniotomy.model_construct(**old_subj_procedure)
    
    def upgrade_fiber_implant(old_subj_procedure: dict):
        """Map legacy FiberImplant model to current version"""
        print("upgrading fiber implant")
        logging.info("FIBER IMPLANT: ", old_subj_procedure.keys())

        probes = []
        for probe in old_subj_procedure.get("probes", []):
            logging.info("PROBE: ", probe)
            for field in probe.keys():
                logging.info(f'FIELD: {field}, Value: {probe[field]}')
            logging.info(f"PROBE: {probe}")
        if check_field(old_subj_procedure, "probes"):
            logging.info("FOUND PROBES")
            if isinstance(old_subj_procedure["probes"], dict):
                logging.info("PROBES IS DICT")
                for field in old_subj_procedure["probes"].keys():
                    logging.info(f'FIELD: {field}, Value: {old_subj_procedure["probes"][field]}')
                probes.append(OphysProbe.model_construct(old_subj_procedure["probes"]))
            elif isinstance(old_subj_procedure["probes"], list):
                logging.info("PROBES IS LIST")
                for probe in old_subj_procedure["probes"]:
                    for field in probe.keys():
                        logging.info(f'FIELD: {field}, Value: {probe[field]}', )
                    probe['core_diameter_unit'] = "um"
                    drop_unused_fields(probe, "ophys_probe")
                    new_probe = OphysProbe.model_construct(probe)
                    probes.append(new_probe)

        try:
            return FiberImplant(
                protocol_id="unknown",
                probes=probes,
            )
        except ValidationError as e:
            logging.error(f"Error validating Fiber: {e}")
            return FiberImplant.model_construct(old_subj_procedure)
    
    def upgrade_headframe(old_subj_procedure: dict):
        """Map legacy Headframe model to current version"""

        if not check_field(old_subj_procedure, "protocol_id"):
            old_subj_procedure["protocol_id"] = "unknown"

        if not check_field(old_subj_procedure, "headframe_part_number"):
            old_subj_procedure["headframe_part_number"] = "unknown"

        try:
            return Headframe.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating Headframe: {e}")
            return Headframe.model_construct(**old_subj_procedure)
    
    def upgrade_intra_cerebellar_ventricle_injection(old_subj_procedure: dict):
        """Map legacy IntraCerebellarVentricleInjection model to current version"""

        try:
            return IntraCerebellarVentricleInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating IntraperitonealInjection: {e}")
            return IntraCerebellarVentricleInjection.model_construct(**old_subj_procedure)
    
    def upgrade_intra_cisternal_magna_injection(old_subj_procedure: dict):  
        """Map legacy IntraCisternalMagnaInjection model to current version"""

        try:
            return IntraCisternalMagnaInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating IntraCisternalMagnaInjection: {e}")
            return IntraCisternalMagnaInjection.model_construct(**old_subj_procedure)
    
    def upgrade_intraperitoneal_injection(old_subj_procedure: dict):
        """Map legacy IntraperitonealInjection model to current version"""

        try:
            return IntraperitonealInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating IntraperitonealInjection: {e}")
            return IntraperitonealInjection.model_construct(**old_subj_procedure)
    
    def upgrade_iontophoresis_injection(old_subj_procedure: dict):
        """Map legacy IontophoresisInjection model to current version"""

        try:
            return IontophoresisInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating IontophoresisInjection: {e}")
            return IontophoresisInjection.model_construct(**old_subj_procedure)
    
    def upgrade_nanoject_injection(old_subj_procedure: dict):
        """Map legacy NanojectInjection model to current version"""

        if not check_field(old_subj_procedure, "injection_materials"):
            old_subj_procedure["injection_materials"] = [None]

        if not check_field(old_subj_procedure, "protocol_id"):
            old_subj_procedure["protocol_id"] = "dx.doi.org/10.17504/protocols.io.bgpujvnw"

        try:
            return NanojectInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating NanojectInjection: {e}")
            return NanojectInjection.model_construct(**old_subj_procedure)
            logging.info(f"Constructed NanojectInjection: {constructed}")
            return NanojectInjection(
                protocol_id="dx.doi.org/10.17504/protocols.io.bgpujvnw",
                injection_coordinate_ml=get_or_default(constructed, "injection_coordinate_ml", {}),
                injection_coordinate_ap=get_or_default(constructed, "injection_coordinate_ap", {}),
                injection_coordinate_depth=get_or_default(constructed, "injection_coordinate_depth", {}),
                injection_coordinate_unit=get_or_default(constructed, "injection_coordinate_unit", {}),
                injection_coordinate_reference=get_or_default(constructed, "injection_coordinate_reference", {}),
                bregma_to_lambda_distance=get_or_default(constructed, "bregma_to_lambda_distance", {}),
                bregma_to_lambda_unit=get_or_default(constructed, "bregma_to_lambda_unit", {}),
                injection_angle=get_or_default(constructed, "injection_angle", {}),
                injection_angle_unit=get_or_default(constructed, "injection_angle_unit", {}),
                targeted_structure=get_or_default(constructed, "targeted_structure", {}),
                injection_hemisphere=get_or_default(constructed, "injection_hemisphere", {}),
                procedure_type=get_or_default(constructed, "procedure_type", {}),
                injection_volume=get_or_default(constructed, "injection_volume", {}),
                injection_volume_unit=get_or_default(constructed, "injection_volume_unit", {}),
            )
    
    def upgrade_perfusion(old_subj_procedure: dict):
        """Map legacy Perfusion model to current version"""

        
        for field in ["protocol_id"]:
            protocol_id = check_field(old_subj_procedure, field)
            if protocol_id:
                break

        if not protocol_id:
            protocol_id = "dx.doi.org/10.17504/protocols.io.bg5vjy66"

        return Perfusion(
            protocol_id=protocol_id,
            output_specimen_ids=set(str(id) for id in old_subj_procedure.get("output_specimen_ids")),
        )
    
    def upgrade_other_subject_procedure(old_subj_procedure: dict): 
        """Map legacy OtherSubjectProcedure model to current version"""

        try:
            return OtherSubjectProcedure.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating OtherSubjectProcedure: {e}")
            return OtherSubjectProcedure.model_construct(old_subj_procedure)
    
    def upgrade_retro_orbital_injection(old_subj_procedure: dict):
        """Map legacy RetroOrbitalInjection model to current version"""
        logging.info(f"Upgrading retro-orbital injection {old_subj_procedure}")

        try:
            return RetroOrbitalInjection.model_validate(old_subj_procedure)
        except ValidationError as e:
            logging.error(f"Error validating RetroOrbitalInjection: {e}")
            return RetroOrbitalInjection.model_construct(old_subj_procedure)
        


class ProcedureUpgrade(BaseModelUpgrade):
    """Handle upgrades for Procedure models."""

    upgrade_funcs = {
        "Craniotomy": SubjectProcedureModelsUpgrade.upgrade_craniotomy,
        "Fiber implant": SubjectProcedureModelsUpgrade.upgrade_fiber_implant,
        "Headframe": SubjectProcedureModelsUpgrade.upgrade_headframe,
        "Intra cerebellar ventricle injection": SubjectProcedureModelsUpgrade.upgrade_intra_cerebellar_ventricle_injection,
        "Intra cisternal magna injection": SubjectProcedureModelsUpgrade.upgrade_intra_cisternal_magna_injection,
        "Intraperitoneal injection": SubjectProcedureModelsUpgrade.upgrade_intraperitoneal_injection,
        "Iontophoresis injection": SubjectProcedureModelsUpgrade.upgrade_iontophoresis_injection,
        "Nanoject injection": SubjectProcedureModelsUpgrade.upgrade_nanoject_injection,
        "Perfusion": SubjectProcedureModelsUpgrade.upgrade_perfusion,
        "Other subject procedure": SubjectProcedureModelsUpgrade.upgrade_other_subject_procedure,
        "Retro-orbital injection": SubjectProcedureModelsUpgrade.upgrade_retro_orbital_injection,
    }

    def caller(self, func, model):
        return func(model)


    def __init__(self, old_procedures_model: Procedures):
        super().__init__(old_procedures_model, model_class=Procedures)

    
    def upgrade_subject_procedure(self, old_subj_procedure: dict):
        """Map legacy SubjectProcedure model to current version"""

        procedure_type = old_subj_procedure.get("procedure_type")
        if procedure_type in self.upgrade_funcs.keys():

            old_subj_procedure = drop_unused_fields(old_subj_procedure, procedure_type)
            
            if check_field(old_subj_procedure, "injection_materials"):
                old_subj_procedure["injection_materials"] = InjectionMaterialsUpgrade.upgrade_injection_materials(old_subj_procedure["injection_materials"])
            elif hasattr(old_subj_procedure, "injection_materials"):
                old_subj_procedure["injection_materials"] = [None]

            return self.caller(self.upgrade_funcs[procedure_type], old_subj_procedure)
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

        if semver.Version.parse(self._get_or_default(self.old_model, "schema_version", {})) <= semver.Version.parse("0.11.0"):
            subj_id = self.old_model.subject_id

            loaded_subject_procedures = {}
            logging.info(f"Upgrading procedures {type(self.old_model.subject_procedures)}")
            for subj_procedure in self.old_model.subject_procedures: #type: dict
                
                date = subj_procedure.get("start_date")


                logging.info(f"Upgrading procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}")
                logging.info(f"Old procedure: {subj_procedure}")

                # upgraded_subj_procedure = self.upgrade_subject_procedure(old_subj_procedure=subj_procedure)
                # logging.info(f"repeat procedure: {subj_procedure}")
                # logging.info(f"Upgraded procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date} to {upgraded_subj_procedure}")
                # if not upgraded_subj_procedure:
                #     continue
                

                if date not in loaded_subject_procedures.keys():
                    logging.info(f"Creating new surgery for subject {subj_id} on date {date}")
                    logging.info(f"from {subj_procedure}")
                    new_surgery = Surgery(
                        start_date=date,
                        experimenter_full_name=str(subj_procedure.get("experimenter_full_name")),
                        iacuc_protocol=subj_procedure.get("iacuc_protocol"),
                        animal_weight_prior=subj_procedure.get("animal_weight_prior"),
                        animal_weight_post=subj_procedure.get("animal_weight_post"),
                        weight_unit=subj_procedure.get("weight_unit", Surgery.model_fields["weight_unit"].default),
                        anaesthesia=subj_procedure.get("anaesthesia"),
                        workstation_id=subj_procedure.get("workstation_id"),
                        notes=subj_procedure.get("notes"),
                        procedures=[self.upgrade_subject_procedure(old_subj_procedure=subj_procedure)],
                        
                    )
                    logging.info(f"new surgery: {new_surgery}")
                    loaded_subject_procedures[date] = new_surgery
                else:
                    logging.info(f"Adding procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}")
                    loaded_subject_procedures[date].procedures.append(self.upgrade_subject_procedure(old_subj_procedure=subj_procedure))
                
            loaded_spec_procedures = []
            for spec_procedure in self.old_model.specimen_procedures:
                date = spec_procedure.start_date

                logging.info(f"Upgrading procedure {spec_procedure.get('procedure_type')} for subject {subj_id} on date {date}")

                upgraded_spec_procedure = ProcedureUpgrade.upgrade_specimen_procedure(spec_procedure)
                
                if not upgraded_spec_procedure:
                    continue
                
                loaded_spec_procedures.append(upgraded_spec_procedure)

            logging.info(f"Creating new procedure for subject {subj_id}")
            logging.info(f"Subject procedures: {loaded_subject_procedures}")
            logging.info(f"Specimen procedures: {loaded_spec_procedures}")
            new_procedure = Procedures(
                subject_id=subj_id,
                subject_procedures=list(loaded_subject_procedures.values()),
                specimen_procedures=loaded_spec_procedures,
                notes=self.old_model.notes,
            )

            return new_procedure