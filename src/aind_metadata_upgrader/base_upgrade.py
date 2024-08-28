"""Module to contain base code to upgrade old models"""

from abc import ABC
from typing import Any, Type, Union

from aind_data_schema.base import AindModel
from pydantic.fields import PydanticUndefined


class BaseModelUpgrade(ABC):
    """Base class for handling upgrades for models"""

    def __init__(self, old_model: Union[dict, AindModel], model_class: Type[AindModel], allow_validation_errors=False):
        """
        Handle mapping of old AindModel model versions into current models

        Parameters
        ----------
        old_model : Union[AindModel, dict]
            The old model to upgrade
        model_class : Type[AindModel]
            The class of the model
        """
        if isinstance(old_model, model_class):
            self.old_model_dict = old_model.model_dump()
        else:
            self.old_model_dict = old_model
        self.model_class = model_class
        self.allow_validation_errors = allow_validation_errors

    def _get_or_default(self, model: dict, field_name: str, kwargs: dict) -> Any:
        """
        If field is not explicitly set, will attempt to extract from a model.
        If field is not found in old model, will attempt to set using the default.

        Parameters
        ----------
        model : AindModel
          Old model to extract value
        field_name : str
          Name of the field
        kwargs : dict
          Explicit args that will override everything else

        Returns
        -------
        Any

        """
        if kwargs.get(field_name) is not None:
            return kwargs.get(field_name)

        elif isinstance(model, dict) and field_name in model.keys() and model.get(field_name) is not None:
            return model.get(field_name)
        else:
            try:
                attr_default = getattr(self.model_class.model_fields.get(field_name), "default")
                if attr_default == PydanticUndefined:
                    return None
                return attr_default
            except AttributeError:
                return None
