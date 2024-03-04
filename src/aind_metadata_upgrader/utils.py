import logging

from aind_data_schema.base import AindModel
from aind_data_schema.core.procedures import (
    Craniotomy,
    FiberImplant,
    Headframe,
    IntraCerebellarVentricleInjection,
    IntraCisternalMagnaInjection,
    IntraperitonealInjection,
    IontophoresisInjection,
    NanojectInjection,
    OphysProbe,
    OtherSubjectProcedure,
    Perfusion,
    RetroOrbitalInjection,
)
from pydantic import ValidationError
from pydantic.fields import PydanticUndefined


def construct_new_model(model_inputs: dict, model_type: AindModel, allow_validation_errors=False):
    """Validate a model, if it fails and validation error flag is on, construct a model"""

    try:
        return model_type.model_validate(model_inputs)
    except ValidationError as e:
        logging.error(f"Validation error in {type(model_type)}: {e}")
        return model_type.model_construct(**model_inputs)


def check_field(model, field):
    """Check if field exists in model and is not None, return the value if it exists, else return None"""

    if hasattr(model, field) and getattr(model, field) is not None:
        return getattr(model, field)
    return None


def get_or_default(model: dict, model_type: AindModel, field_name: str, kwargs: dict = {}):
    """Version of get_or_default that works with a dict instead of a model instance. If field is not explicitly set, will attempt to extract from a model."""

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
    """Drop fields from a dict that are not in the model type given"""

    remove_fields = []
    for field in item.keys():
        if field not in procedure_types_list[model_type].model_fields.keys():
            remove_fields.append(field)
    for field in remove_fields:
        item.pop(field)

    return item
