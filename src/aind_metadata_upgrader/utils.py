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
        if allow_validation_errors:
            return model_type.model_construct(**model_inputs)
        else:
            return None


def get_or_default(model: dict, model_type: AindModel, field_name: str):
    """Version of get_or_default that works with a dict instead of a model instance. If field is not explicitly set, will attempt to extract from a model."""

    if model.get(field_name, None) is not None:
        return model.get(field_name)
    else:
        try:
            attr_default = getattr(model_type.model_fields.get(field_name), "default")
            if attr_default == PydanticUndefined:
                return None
            return attr_default
        except AttributeError:
            return None
