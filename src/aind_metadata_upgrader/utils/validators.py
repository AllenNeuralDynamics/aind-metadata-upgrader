"""Validator utility functions with fixed implementations"""

from enum import Enum
from typing import Any, List


def recursive_get_all_names(obj: Any) -> List[str]:
    """
    Recursively extract all 'name' fields from an object and its nested fields.

    This is a fixed version that properly handles dictionaries and tuples,
    addressing issues in the original aind_data_schema.utils.validators implementation.

    Args:
        obj: Any object to extract names from (objects, dictionaries, lists, tuples, etc.)

    Returns:
        List of all string 'name' fields found in the object and its nested structures
    """
    names = []

    if obj is None or isinstance(obj, Enum):  # Skip None and Enums
        return names

    elif isinstance(obj, (str, int, float, bool)):  # Skip primitive types to avoid issues
        return names

    elif isinstance(obj, dict):  # Handle dictionaries
        if "name" in obj and isinstance(obj["name"], str):  # Ensure name is a string
            names.append(obj["name"])
        for value in obj.values():
            names.extend(recursive_get_all_names(value))

    elif isinstance(obj, (list, tuple)):  # Handle lists and tuples
        for item in obj:
            names.extend(recursive_get_all_names(item))

    elif hasattr(obj, "__dict__"):  # Handle objects (including Pydantic models)
        if hasattr(obj, "name") and isinstance(obj.name, str):  # Ensure name is a string
            names.append(obj.name)
        for field_value in vars(obj).values():  # Use vars() for robustness
            names.extend(recursive_get_all_names(field_value))

    return names
