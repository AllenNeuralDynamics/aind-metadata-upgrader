"""Shared helpers for the v2.x to v3.0 upgraders

biodata-schema v3 is aind-data-schema v2.9 with the deprecated fields removed. The helpers
here walk a core file dictionary and apply per-object_type rewrites.
"""

import importlib
import inspect
import pkgutil
from typing import Any, Callable, Optional

import biodata_schema
from pydantic import BaseModel
from pydantic_core import PydanticUndefined


def _walk_models():
    """Yield every pydantic model defined in the biodata_schema package"""
    for _, name, _ in pkgutil.walk_packages(biodata_schema.__path__, f"{biodata_schema.__name__}."):
        try:
            module = importlib.import_module(name)
        except Exception:  # pragma: no cover - optional submodules
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseModel) and cls.__module__.startswith(biodata_schema.__name__):
                yield cls


def _build_lookups() -> tuple[dict, dict]:
    """Map object_type to the renamed coordinate_system field and to the v3 describedBy"""
    coordinate_targets = {}
    described_by = {}
    for cls in _walk_models():
        fields = getattr(cls, "model_fields", {})
        object_type_field = fields.get("object_type")
        if object_type_field is None or object_type_field.default is PydanticUndefined:
            continue
        object_type = object_type_field.default
        if "global_coordinate_system" in fields:
            coordinate_targets[object_type] = "global_coordinate_system"
        elif "local_coordinate_system" in fields:
            coordinate_targets[object_type] = "local_coordinate_system"
        described_by_field = fields.get("describedBy")
        if described_by_field is not None and described_by_field.default is not PydanticUndefined:
            described_by[object_type] = described_by_field.default
    return coordinate_targets, described_by


COORDINATE_SYSTEM_TARGETS, DESCRIBED_BY = _build_lookups()


def rename_coordinate_system(node: dict, object_type: Optional[str]) -> None:
    """Fold the removed coordinate_system field into its global_/local_ replacement"""
    target = COORDINATE_SYSTEM_TARGETS.get(object_type)
    if target is None or "coordinate_system" not in node:
        return
    coordinate_system = node.pop("coordinate_system")
    if coordinate_system is not None and node.get(target) is None:
        node[target] = coordinate_system


def repair_described_by(node: dict, object_type: Optional[str]) -> None:
    """Point describedBy at the biodata-schema source instead of aind-data-schema"""
    if "describedBy" in node and object_type in DESCRIBED_BY:
        node["describedBy"] = DESCRIBED_BY[object_type]


def recursive_upgrade(
    data: Any,
    handlers: dict[str, Callable[[dict], None]],
    object_type: Optional[str] = None,
) -> Any:
    """Recursively apply the v2 -> v3 rewrites to a core file payload

    ``handlers`` maps an object_type to a function that mutates the matching object in place.
    The coordinate_system rename and the describedBy repair are applied to every object.
    ``object_type`` names the root object for upgraders that build plain dicts without an
    ``object_type`` key.
    """
    if isinstance(data, BaseModel):
        data = data.model_dump()
    if isinstance(data, list):
        return [recursive_upgrade(item, handlers) for item in data]
    if not isinstance(data, dict):
        return data

    node = dict(data)
    node_type = node.get("object_type", object_type)

    rename_coordinate_system(node, node_type)
    handler = handlers.get(node_type)
    if handler is not None:
        handler(node)
    repair_described_by(node, node_type)

    return {key: recursive_upgrade(value, handlers) for key, value in node.items()}
