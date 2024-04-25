"""Utilities for upgrading metadata models."""

import logging

from aind_data_schema.base import AindModel
from pydantic import ValidationError
from pydantic.fields import PydanticUndefined


def construct_new_model(model_inputs: dict, model_type: AindModel, allow_validation_errors=False):
    """Validate a model, if it fails and validation error flag is on, construct a model"""

    try:
        return model_type.model_validate(model_inputs)
    except ValidationError as e:
        logging.error(f"Validation error in {type(model_type)}: {e}")
        logging.error(f"allow validation errors: {allow_validation_errors}")
        if allow_validation_errors:
            logging.error(f"Attempting to construct model {model_inputs}")
            m = model_type.model_construct(**model_inputs)
            logging.error(f"Model constructed: {m}")
            return m
        else:
            raise e


def get_or_default(model: dict, model_type: AindModel, field_name: str):
    """Version of get_or_default that works with a dict instead of a model instance.
    If field is not explicitly set, will attempt to extract from a model."""

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
