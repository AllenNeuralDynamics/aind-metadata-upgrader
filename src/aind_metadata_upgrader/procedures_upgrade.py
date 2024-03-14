"""Module to contain code to uprgade old procedures"""

import logging
from typing import Any, Optional, Union

from decimal import Decimal

import semver
from aind_data_schema.core.procedures import (
    Craniotomy,
    FiberImplant,
    Headframe,
    IntraCerebellarVentricleInjection,
    IntraCisternalMagnaInjection,
    IntraperitonealInjection,
    IontophoresisInjection,
    NanojectInjection,
    NonViralMaterial,
    OphysProbe,
    OtherSubjectProcedure,
    Perfusion,
    Procedures,
    RetroOrbitalInjection,
    SpecimenProcedure,
    Surgery,
    TarsVirusIdentifiers,
    ViralMaterial,
    CraniotomyType,
)
from aind_data_schema.models.devices import FiberProbe

from aind_metadata_upgrader.base_upgrade import BaseModelUpgrade
from aind_metadata_upgrader.utils import *


class InjectionMaterialsUpgrade():
    """Handle upgrades for InjectionMaterials models."""

    def __init__(self, allow_validation_errors=False):
        """Handle upgrades for InjectionMaterials models"""

        self.allow_validation_errors = allow_validation_errors

    def upgrade_viral_material(self, material: dict) -> ViralMaterial:
        """Map legacy NonViralMaterial model to current version"""

        if material.get("tars_identifiers", None):
            tars_data = material.get("tars_identifiers")

            tars_identifier = construct_new_model(tars_data, TarsVirusIdentifiers, self.allow_validation_errors)
        else:
            tars_identifier = None

        viral_dict = {
            "name": material.get("name", "unknown"),
            "tars_identifiers": tars_identifier,
            "addgene_id": material.get("addgene_id", None),
            "titer": material.get("titer", None),
            "titer_unit": material.get("titer_unit", None),
        }

        return construct_new_model(viral_dict, ViralMaterial, self.allow_validation_errors)

    def upgrade_nonviral_material(self, material: dict) -> NonViralMaterial:
        """Map legacy NonViralMaterial model to current version"""

        nonviral_dict = {
            "concentration": material.get("concentration", None),
            "concentration_unit": get_or_default(material, NonViralMaterial, "concentration_unit"),
            "name": material.get("name", "unknown"),
            "source": get_or_default(material, NonViralMaterial, "source"),
            "rrid": get_or_default(material, NonViralMaterial, "rrid"),
            "lot_number": material.get("lot_number", None),
            "expiration_date": get_or_default(material, NonViralMaterial, "expiration_date"),
        }

        return construct_new_model(nonviral_dict, NonViralMaterial, self.allow_validation_errors)


    def upgrade_injection_materials(self, old_injection_materials: list) -> Optional[dict]:
        """Map legacy InjectionMaterials model to current version"""

        new_materials = []
        if isinstance(old_injection_materials, list):
            for (
                injection_material
            ) in old_injection_materials:  # this wont work like i want, we changed the naming convention
                if injection_material.get("titer") is not None:
                    new_materials.append(self.upgrade_viral_material(injection_material))

                elif injection_material.get("concentration") is not None:
                    new_materials.append(self.upgrade_nonviral_material(injection_material))
                else:
                    logging.error(f"Injection material with no titer or concentration {injection_material} passed in")
        else:
            logging.error(f"injection materials not a list: {old_injection_materials}")

        logging.info(f"new_materials: {new_materials}")
        return new_materials


class SubjectProcedureModelsUpgrade(BaseModelUpgrade):
    """Handle upgrades for SubjectProcedure models."""

    def __init__(self, allow_validation_errors=False):
        """Handle upgrades for SubjectProcedure models"""

        self.allow_validation_errors = allow_validation_errors
        self.injection_upgrader = InjectionMaterialsUpgrade(allow_validation_errors)

    def upgrade_craniotomy(self, old_subj_procedure: dict):
        """Map legacy Craniotomy model to current version"""

        craniotomy_dict = {
            "protocol_id": old_subj_procedure.get("protocol_id", "unknown"),
            "craniotomy_type": old_subj_procedure.get("craniotomy_type", None),
            "craniotomy_hemisphere": get_or_default(old_subj_procedure, Craniotomy, "craniotomy_hemisphere"),
            "bregma_to_lambda_distance": old_subj_procedure.get("bregma_to_lambda_distance", None),
            "bregma_to_lambda_unit": get_or_default(old_subj_procedure, Craniotomy, "bregma_to_lambda_unit"),
            "implant_part_number": old_subj_procedure.get("implant_part_number", None),
            "dura_removed": get_or_default(old_subj_procedure, Craniotomy, "dura_removed"),
            "protective_material": get_or_default(old_subj_procedure, Craniotomy, "protective_material"),
            "recovery_time": old_subj_procedure.get("recovery_time", None),
            "recovery_time_unit": get_or_default(old_subj_procedure, Craniotomy, "recovery_time_unit"),
        }

        craniotomy_size = old_subj_procedure.get("craniotomy_size", None),

        if not craniotomy_dict['craniotomy_type'] and craniotomy_size:
            if '3' in craniotomy_size:
                craniotomy_dict['craniotomy_type'] = '3 mm'
            elif '5' in craniotomy_size:
                craniotomy_dict['craniotomy_type'] = '5 mm'
            
        return construct_new_model(craniotomy_dict, Craniotomy, self.allow_validation_errors)


    def construct_ophys_probe(self, probe: dict):
        """Map legacy OphysProbe model to current version"""

        if probe.get("ophys_probe") is not None:
            fiber_probe_item = probe.get("ophys_probe")
            fiber_probe_dict = {
                "device_type": probe.get("device_type", None),
                "name": probe.get("name", None),
                "serial_number": probe.get("serial_number", None),
                "manufacturer": probe.get("manufacturer", None),
                "model": probe.get("model", None),
                "path_to_cad": probe.get("path_to_cad", None),
                "port_index": probe.get("port_index", None),
                "additional_set": get_or_default(probe, OphysProbe, "additional_set"),
                "core_diameter": fiber_probe_item.get("core_diameter", None),
                "core_diameter_unit": fiber_probe_item.get("core_diameter_unit", None),
                "numerical_aperture": fiber_probe_item.get("numerical_aperture", None),
                "ferrule_material": fiber_probe_item.get("ferrule_material", None),
                "active_length": fiber_probe_item.get("active_length", None),
                "total_length": fiber_probe_item.get("total_length", None),
                "length_unit": get_or_default(fiber_probe_item, FiberProbe, "length_unit"),
            }
            fiber_probe = construct_new_model(fiber_probe_dict, FiberProbe, self.allow_validation_errors)
        else:
            # fiber_probe = FiberProbe.model_construct()
            fiber_probe = None

        ophys_probe_dict = {
            "ophys_probe": fiber_probe,
            "targeted_structure": probe.get("targeted_structure", "unknown"),
            "stereotactic_coordinate_ap": Decimal(probe.get("stereotactic_coordinate_ap", None)),
            "stereotactic_coordinate_ml": Decimal(probe.get("stereotactic_coordinate_ml", None)),
            "stereotactic_coordinate_dv": Decimal(probe.get("stereotactic_coordinate_dv", None)),
            "stereotactic_coordinate_unit": get_or_default(probe, OphysProbe, "stereotactic_coordinate_unit"),
            "stereotactic_coordinate_reference": probe.get("stereotactic_coordinate_reference", None),
            "bregma_to_lambda_distance": probe.get("bregma_to_lambda_distance", None),
            "bregma_to_lambda_unit": get_or_default(probe, OphysProbe, "bregma_to_lambda_unit"),
            "angle": probe.get("angle", None),
            "angle_unit": get_or_default(probe, OphysProbe, "angle_unit"),
            "notes": get_or_default(probe, OphysProbe, "notes"),
        }

        return construct_new_model(ophys_probe_dict, OphysProbe, self.allow_validation_errors)

    def upgrade_fiber_implant(self, old_subj_procedure: dict):
        """Map legacy FiberImplant model to current version"""

        probes = []

        if "probes" in old_subj_procedure.keys():
            if isinstance(old_subj_procedure["probes"], dict):
                probe = old_subj_procedure["probes"]
                new_probe = self.construct_ophys_probe(probe)
                if new_probe:
                    probes.append(new_probe)

            elif isinstance(old_subj_procedure["probes"], list):
                for probe in old_subj_procedure["probes"]:
                    new_probe = self.construct_ophys_probe(probe)
                    if new_probe:
                        probes.append(new_probe)

        fiber_implant_dict = {
            "protocol_id": old_subj_procedure.get("protocol_id", "unknown"), 
            "probes": probes
        }

        return construct_new_model(fiber_implant_dict, FiberImplant, self.allow_validation_errors)


    def add_probe(self, old_subj_procedure: dict, fiber_implant_model: FiberImplant):
        """adds a probe to an existing fiber implant model"""

        fiber_implant_model.probes.append(self.construct_ophys_probe(old_subj_procedure["probes"]))
        


    def upgrade_headframe(self, old_subj_procedure: dict):
        """Map legacy Headframe model to current version"""

        # headframe part number could be optional

        headframe_dict = {
            "protocol_id": old_subj_procedure.get("protocol_id", "unknown"),
            "headframe_part_number": old_subj_procedure.get("headframe_part_number", "unknown"),
            "headframe_type": old_subj_procedure.get("headframe_type", "unknown"),
            "headframe_material": get_or_default(old_subj_procedure, Headframe, "headframe_material"),
            "well_part_number": get_or_default(old_subj_procedure, Headframe, "well_part_number"),
            "well_type": get_or_default(old_subj_procedure, Headframe, "well_type"),
        }

        return construct_new_model(headframe_dict, Headframe, self.allow_validation_errors)


    def upgrade_nanoject_injection(self, old_subj_procedure: dict):
        """Map legacy NanojectInjection model to current version"""

        injection_dict = {
            "injection_volume": old_subj_procedure.get("injection_volume", None),
            "injection_volume_unit": get_or_default(old_subj_procedure, NanojectInjection, "injection_volume_unit"),
            "injection_materials": old_subj_procedure.get("injection_materials", [None]),
            "recovery_time": old_subj_procedure.get("recovery_time", None),
            "recovery_time_unit": get_or_default(old_subj_procedure, NanojectInjection, "recovery_time_unit"),
            "injection_duration": old_subj_procedure.get("injection_duration", None),
            "injection_duration_unit": get_or_default(old_subj_procedure, NanojectInjection, "injection_duration_unit"),
            "instrument_id": old_subj_procedure.get("instrument_id", None),
            "protocol_id": old_subj_procedure.get("protocol_id", "dx.doi.org/10.17504/protocols.io.bgpujvnw"),
            "injection_coordinate_ml": old_subj_procedure.get("injection_coordinate_ml", None),
            "injection_coordinate_ap": old_subj_procedure.get("injection_coordinate_ap", None),
            "injection_coordinate_depth": old_subj_procedure.get("injection_coordinate_depth", None),
            "injection_coordinate_unit": get_or_default(
                old_subj_procedure, NanojectInjection, "injection_coordinate_unit"
            ),
            "injection_coordinate_reference": old_subj_procedure.get("injection_coordinate_reference", None),
            "bregma_to_lambda_distance": old_subj_procedure.get("bregma_to_lambda_distance", None),
            "bregma_to_lambda_unit": get_or_default(old_subj_procedure, NanojectInjection, "bregma_to_lambda_unit"),
            "injection_angle": old_subj_procedure.get("injection_angle", None),
            "injection_angle_unit": get_or_default(old_subj_procedure, NanojectInjection, "injection_angle_unit"),
            "targeted_structure": old_subj_procedure.get("targeted_structure", None),
            "injection_hemisphere": old_subj_procedure.get("injection_hemisphere", None),
        }

        return construct_new_model(injection_dict, NanojectInjection, self.allow_validation_errors)

    def upgrade_perfusion(self, old_subj_procedure: dict):
        """Map legacy Perfusion model to current version"""

        perfusion_dict = {
            "protocol_id": old_subj_procedure.get("protocol_id", "dx.doi.org/10.17504/protocols.io.bg5vjy66"),
            "output_specimen_ids": [str(item) for item in old_subj_procedure.get("output_specimen_ids", [])],
        }

        return construct_new_model(perfusion_dict, Perfusion, self.allow_validation_errors)


    def upgrade_retro_orbital_injection(self, old_subj_procedure: dict):
        """Map legacy RetroOrbitalInjection model to current version"""

        retro_orbital_dict = {
            "injection_volume": old_subj_procedure.get("injection_volume", None),
            "injection_volume_unit": get_or_default(old_subj_procedure, RetroOrbitalInjection, "injection_volume_unit"),
            "injection_eye": old_subj_procedure.get("injection_eye", "unknown"),
            "injection_materials": old_subj_procedure.get("injection_materials", None),
            "recovery_time": old_subj_procedure.get("recovery_time", None),
            "recovery_time_unit": get_or_default(old_subj_procedure, RetroOrbitalInjection, "recovery_time_unit"),
            "injection_duration": old_subj_procedure.get("injection_duration", None),
            "injection_duration_unit": get_or_default(
                old_subj_procedure, RetroOrbitalInjection, "injection_duration_unit"
            ),
            "instrument_id": old_subj_procedure.get("instrument_id", None),
            "protocol_id": old_subj_procedure.get("protocol_id", "unknown"),
        }

        return construct_new_model(retro_orbital_dict, RetroOrbitalInjection, self.allow_validation_errors)


def set_craniotomy_type(surgery: Surgery): # find a better organizational place for this
    craniotomy = [x for x in surgery.procedures if isinstance(x, Craniotomy)][0]
    if any(isinstance(x, Headframe) for x in surgery.procedures):
        
        headframe = [x for x in surgery.procedures if isinstance(x, Headframe)][0]
        if hasattr(headframe, 'headframe_type'):
            if 'WHC' in headframe.headframe_type:
                logging.debug(f"replacing craniotomy type in {craniotomy}")
                craniotomy.craniotomy_type = CraniotomyType.WHC
            elif 'Ctx' in headframe.headframe_type:
                logging.debug(f"replacing craniotomy type in {craniotomy}")
                craniotomy.craniotomy_type = CraniotomyType.VISCTX


class ProcedureUpgrade(BaseModelUpgrade):
    """Handle upgrades for Procedure models."""

    def __init__(self, old_procedures_model: Union[Procedures, dict], allow_validation_errors=False):
        """Handle upgrades for Procedure models"""

        super().__init__(old_procedures_model, model_class=Procedures, allow_validation_errors=allow_validation_errors)

        self.subj_procedure_upgrader = SubjectProcedureModelsUpgrade(allow_validation_errors)

        self.upgrade_funcs = {
            "Craniotomy": self.subj_procedure_upgrader.upgrade_craniotomy,
            "Fiber implant": self.subj_procedure_upgrader.upgrade_fiber_implant,
            "Headframe": self.subj_procedure_upgrader.upgrade_headframe,
            "Nanoject injection": self.subj_procedure_upgrader.upgrade_nanoject_injection,
            "Perfusion": self.subj_procedure_upgrader.upgrade_perfusion,
            "Retro-orbital injection": self.subj_procedure_upgrader.upgrade_retro_orbital_injection,
        }

    def caller(self, func, model):
        """Call a function with a model as an argument"""

        return func(model)

    def upgrade_subject_procedure(self, old_subj_procedure: dict):
        """Map legacy SubjectProcedure model to current version"""

        procedure_type = old_subj_procedure.get("procedure_type")
        if procedure_type in self.upgrade_funcs.keys():

            if old_subj_procedure.get("injection_materials"):
                old_subj_procedure["injection_materials"] = InjectionMaterialsUpgrade(
                    self.allow_validation_errors
                ).upgrade_injection_materials(old_subj_procedure["injection_materials"])
            else:
                old_subj_procedure["injection_materials"] = [None]

            return self.caller(self.upgrade_funcs[procedure_type], old_subj_procedure)
        else:
            logging.error(f"Procedure type {procedure_type} not found in list of procedure types")
            return None

    @staticmethod
    def upgrade_specimen_procedure(self, old_specimen_procedure: Any) -> Optional[SpecimenProcedure]:
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

        if semver.Version.parse(self._get_or_default(self.old_model, "schema_version", {})) <= semver.Version.parse(
            "0.11.0"
        ):
            subj_id = self.old_model.subject_id

            loaded_subject_procedures = {}
            logging.info(f"Upgrading procedures {type(self.old_model.subject_procedures)}")
                
            for subj_procedure in self.old_model.subject_procedures:  # type: dict

                logging.info("intro")

                date = subj_procedure.get("start_date")

                logging.info(
                    f"Upgrading procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}"
                )
                logging.info(f"Old procedure: {subj_procedure}")

                if date not in loaded_subject_procedures.keys():
                    logging.info(f"Creating new surgery for subject {subj_id} on date {date}")
                    logging.info(f"from {subj_procedure}")
                    new_surgery_dict = {
                        "start_date":date,
                        "experimenter_full_name":str(subj_procedure.get("experimenter_full_name")),
                        "iacuc_protocol":subj_procedure.get("iacuc_protocol"),
                        "animal_weight_prior":subj_procedure.get("animal_weight_prior"),
                        "animal_weight_post":subj_procedure.get("animal_weight_post"),
                        "weight_unit":subj_procedure.get("weight_unit", Surgery.model_fields["weight_unit"].default),
                        "anaesthesia":subj_procedure.get("anaesthesia"),
                        "workstation_id":subj_procedure.get("workstation_id"),
                        "notes":subj_procedure.get("notes"),
                        "procedures":[self.upgrade_subject_procedure(old_subj_procedure=subj_procedure)],
                    }
                    logging.info(f"new surgery: {new_surgery_dict}")
                    loaded_subject_procedures[date] = new_surgery_dict
                    logging.info(f"huh?? {loaded_subject_procedures[date]}")
                    logging.info(f"keys: {loaded_subject_procedures.keys()}")
                else:
                    logging.info(
                        f"Adding procedure {subj_procedure.get('procedure_type')} for subject {subj_id} on date {date}"
                    )
                    
                    if subj_procedure.get("procedure_type") == 'Fiber implant' and any(isinstance(x, FiberImplant) for x in loaded_subject_procedures[date]['procedures']):
                        logging.info(f"Adding probe to existing fiber implant for subject {subj_id} on date {date}")
                        existing_retro = [x for x in loaded_subject_procedures[date]['procedures'] if isinstance(x, FiberImplant)]
                        SubjectProcedureModelsUpgrade().add_probe(subj_procedure, existing_retro[0])
                    else:
                        logging.info(f"Adding procedure to existing surgery for subject {subj_id} on date {date}: {subj_procedure}")
                        loaded_subject_procedures[date]['procedures'].append(
                            self.upgrade_subject_procedure(old_subj_procedure=subj_procedure)
                        )

            logging.info(f"loaded_subject_procedures: {loaded_subject_procedures.keys()}")
            logging.info("trying stuff")
            constructed_subject_procedures = {date: construct_new_model(surgery, Surgery, self.allow_validation_errors) for date, surgery in loaded_subject_procedures.items()}

            for surgery in constructed_subject_procedures.values():
                logging.info(f"Setting craniotomy type for subject {subj_id}, surgery: {surgery}")
                if any(isinstance(x, Craniotomy) for x in surgery.procedures):
                    set_craniotomy_type(surgery)
                        

            loaded_spec_procedures = []
            for spec_procedure in self.old_model.specimen_procedures:
                date = spec_procedure.start_date

                logging.info(
                    f"Upgrading procedure {spec_procedure.get('procedure_type')} for subject {subj_id} on date {date}"
                )

                upgraded_spec_procedure = ProcedureUpgrade.upgrade_specimen_procedure(spec_procedure)

                if not upgraded_spec_procedure:
                    continue

                loaded_spec_procedures.append(upgraded_spec_procedure)

            logging.info(f"Creating new procedure for subject {subj_id}")
            logging.info(f"Subject procedures: {loaded_subject_procedures}")
            logging.info(f"Specimen procedures: {loaded_spec_procedures}")
            new_procedure = Procedures(
                subject_id=subj_id,
                subject_procedures=list(constructed_subject_procedures.values()),
                specimen_procedures=loaded_spec_procedures,
                notes=self.old_model.notes,
            )

            return new_procedure
        
        else:
            return construct_new_model(self.old_model, Procedures, self.allow_validation_errors)
