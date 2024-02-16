from aind_data_schema.base import AindModel
from pydantic.fields import PydanticUndefined


def check_field(model, field):
    if hasattr(model, field) and getattr(model, field) is not None:
        return getattr(model, field)
    return None

def get_or_default(model: AindModel, field_name: str, kwargs: dict)
    if kwargs.get(field_name) is not None:
        return kwargs.get(field_name)
    elif hasattr(model, field_name) and getattr(model, field_name) is not None:
        return getattr(model, field_name)
    else:
        try:
            attr_default = getattr(type(model).model_fields.get(field_name), "default")
            if attr_default == PydanticUndefined:
                return None
            return attr_default
        except AttributeError:
            return None