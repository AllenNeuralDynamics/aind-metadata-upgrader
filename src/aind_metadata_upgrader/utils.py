from aind_data_schema.base import AindModel
from pydantic.fields import PydanticUndefined

import logging

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


def check_field(model, field):
    if hasattr(model, field) and getattr(model, field) is not None:
        return getattr(model, field)
    return None

def get_or_default(model: dict, model_type: AindModel, field_name: str, kwargs: dict = {}):
    if kwargs.get(field_name) is not None:
        return kwargs.get(field_name)
    elif model.get(field_name, None) is not None:
        logging.info(f"field_name: {field_name}, model.get(field_name): {model.get(field_name)}")
        return model.get(field_name)
    else:
        try:
            attr_default = getattr(model_type.model_fields.get(field_name), "default")
            if attr_default == PydanticUndefined:
                return None
            return attr_default
        except AttributeError:
            return None
        

procedure_types_list = {
    "Craniotomy": Craniotomy,
    "Fiber implant": FiberImplant,
    "Headframe": Headframe,
    "Intra cerebellar ventricle injection": IntraCerebellarVentricleInjection,
    "Intra cisternal magna injection": IntraCisternalMagnaInjection,
    "Intraperitoneal injection": IntraperitonealInjection,
    "Iontophoresis injection": IontophoresisInjection,
    "Nanoject injection": NanojectInjection,
    "Perfusion": Perfusion,
    "Other subject procedure": OtherSubjectProcedure,
    "Retro-orbital injection": RetroOrbitalInjection,
    "ophys_probe": OphysProbe,
}

def drop_unused_fields(item, model_type):
    remove_fields = []
    for field in item.keys():
        if field not in procedure_types_list[model_type].model_fields.keys():
            remove_fields.append(field)
    for field in remove_fields:
        item.pop(field)

    return item