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

TRANSFORM_OBJECT_TYPES = {"Affine", "Rotation", "Scale", "Translation"}
TRANSFORM_FIELDS = {
    "affine_transform",
    "coordinates",
    "image_to_acquisition_transform",
    "local_axis_positions",
    "measured_coordinates",
    "position",
    "transform",
}
VERTICAL_DIRECTIONS_DOWN = {"superior_to_inferior", "top_to_bottom", "up_to_down"}
VERTICAL_DIRECTIONS_UP = {"bottom_to_top", "down_to_up", "inferior_to_superior"}


def _normalise_axis_value(value: Any) -> str:
    """Normalize an axis name or direction for comparisons."""
    value = getattr(value, "value", value)
    return str(value).replace("-", "_").replace(" ", "_").lower()


def _vertical_axis_index(axes: list[dict]) -> Optional[int]:
    """Find the vertical axis in a coordinate system after depth is removed."""
    for index, axis in enumerate(axes):
        direction = _normalise_axis_value(axis.get("direction"))
        if direction in VERTICAL_DIRECTIONS_DOWN or direction in VERTICAL_DIRECTIONS_UP:
            return index
    for index, axis in enumerate(axes):
        if _normalise_axis_value(axis.get("name")) == "z":
            return index
    return None


def _prepare_coordinate_system(coordinate_system: Any) -> Optional[dict]:
    """Remove a legacy depth axis and return context for its transforms."""
    if not isinstance(coordinate_system, dict) or not isinstance(coordinate_system.get("axes"), list):
        return None

    axes = coordinate_system["axes"]
    depth_index = next(
        (
            index
            for index, axis in enumerate(axes)
            if isinstance(axis, dict) and _normalise_axis_value(axis.get("name")) == "depth"
        ),
        None,
    )
    depth_direction = None
    if depth_index is not None:
        depth_direction = _normalise_axis_value(axes[depth_index].get("direction"))
        axes = [axis for index, axis in enumerate(axes) if index != depth_index]
        coordinate_system["axes"] = axes

    return {
        "axis_count": len(axes) + (1 if depth_index is not None else 0),
        "axes": axes,
        "depth_direction": depth_direction,
        "depth_index": depth_index,
        "vertical_axis_index": _vertical_axis_index(axes),
    }


def _depth_index(parameters: list, context: Optional[dict]) -> Optional[int]:
    """Find the legacy depth component in a transform parameter list."""
    if context is None:
        return None
    if context["depth_index"] is not None and len(parameters) == context["axis_count"]:
        return context["depth_index"]
    if len(parameters) == len(context["axes"]) + 1:
        return len(parameters) - 1
    return None


def _depth_sign(depth_direction: Optional[str], axis_direction: str) -> int:
    """Return the sign needed to preserve physical vertical direction."""
    depth_is_down = depth_direction in VERTICAL_DIRECTIONS_DOWN
    depth_is_up = depth_direction in VERTICAL_DIRECTIONS_UP
    axis_is_down = axis_direction in VERTICAL_DIRECTIONS_DOWN
    axis_is_up = axis_direction in VERTICAL_DIRECTIONS_UP
    if (depth_is_down and axis_is_up) or (depth_is_up and axis_is_down):
        return -1
    return 1


def _convert_affine_transform(transform: dict, index: int) -> dict:
    """Remove a depth row and column from a homogeneous affine matrix."""
    matrix = transform.get("affine_transform")
    if not isinstance(matrix, list) or not matrix or not all(isinstance(row, list) for row in matrix):
        return transform
    if len(matrix) != len(matrix[0]) or index >= len(matrix) - 1:
        return transform
    converted = dict(transform)
    converted["affine_transform"] = [
        [value for column, value in enumerate(row) if column != index]
        for row_number, row in enumerate(matrix)
        if row_number != index
    ]
    return converted


def _normalise_affine_transform(transform: dict, context: Optional[dict]) -> dict:
    """Make an affine matrix compatible with the v3 homogeneous representation."""
    matrix = transform.get("affine_transform")
    if not isinstance(matrix, list) or not matrix or not all(isinstance(row, list) for row in matrix):
        return transform
    index = _affine_depth_index(matrix, context)
    converted = _convert_affine_transform(transform, index) if index is not None else transform
    matrix = converted.get("affine_transform")
    axis_count = len(context["axes"]) if context is not None else None
    if axis_count is None or len(matrix) != axis_count or any(len(row) != axis_count for row in matrix):
        return converted
    padded = [row + [0] for row in matrix]
    padded.append([0] * axis_count + [1])
    converted["affine_transform"] = padded
    return converted


def _affine_depth_index(matrix: Any, context: Optional[dict]) -> Optional[int]:
    """Find the depth row and column in a homogeneous affine matrix."""
    if not isinstance(matrix, list) or not matrix or not all(isinstance(row, list) for row in matrix):
        return None
    if len(matrix) != len(matrix[0]):
        return None
    axis_count = len(matrix) - 1
    if context is None:
        return None
    if context["depth_index"] is not None and axis_count == context["axis_count"]:
        return context["depth_index"]
    if axis_count == len(context["axes"]) + 1:
        return len(context["axes"])
    return None


def _convert_transform(transform: dict, context: Optional[dict], separate_local_depth: bool) -> list[dict]:
    """Convert one legacy transform and return one or more v3 transforms."""
    if context is None:
        return [transform]

    object_type = transform.get("object_type")
    parameter_name = {
        "Rotation": "angles",
        "Scale": "scale",
        "Translation": "translation",
    }.get(object_type)
    if parameter_name is None:
        if object_type != "Affine":
            return [transform]
        return [_normalise_affine_transform(transform, context)]

    parameters = transform.get(parameter_name)
    if not isinstance(parameters, list):
        return [transform]
    index = _depth_index(parameters, context)
    if index is None:
        return [transform]

    depth = parameters[index]
    converted = dict(transform)
    converted[parameter_name] = parameters[:index] + parameters[index + 1 :]
    if object_type != "Translation":
        return [converted]

    vertical_index = context["vertical_axis_index"]
    if vertical_index is None:
        return [converted]
    axis_direction = _normalise_axis_value(context["axes"][vertical_index].get("direction"))
    signed_depth = depth * _depth_sign(context["depth_direction"], axis_direction)
    if separate_local_depth:
        local_translation = [0] * len(converted["translation"])
        local_translation[vertical_index] = signed_depth
        return [
            converted,
            {
                "object_type": "Translation",
                "reference_coordinate_system": "local",
                "translation": local_translation,
            },
        ]

    converted["translation"][vertical_index] += signed_depth
    return [converted]


def _upgrade_transform_value(value: Any, context: Optional[dict], separate_local_depth: bool) -> Any:
    """Recursively convert transforms while preserving coordinate list nesting."""
    if isinstance(value, dict):
        if value.get("object_type") in TRANSFORM_OBJECT_TYPES:
            converted = _convert_transform(value, context, separate_local_depth)
            return converted[0] if len(converted) == 1 else _ExpandedTransforms(converted)
        return {key: _upgrade_transform_value(item, context, separate_local_depth) for key, item in value.items()}
    if isinstance(value, list):
        converted = []
        for item in value:
            upgraded = _upgrade_transform_value(item, context, separate_local_depth)
            if isinstance(upgraded, _ExpandedTransforms):
                converted.extend(upgraded)
            else:
                converted.append(upgraded)
        return converted
    return value


class _ExpandedTransforms(list):
    """Internal marker for a transform replaced by a transform sequence."""


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


def repair_code_version(node: dict, object_type: Optional[str]) -> None:
    """Provide a placeholder version for Code objects without one"""
    if object_type == "Code" and not node.get("version"):
        node["version"] = "unknown"


def recursive_upgrade(
    data: Any,
    handlers: dict[str, Callable[[dict], None]],
    object_type: Optional[str] = None,
    _global_coordinate_context: Optional[dict] = None,
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
        return [
            recursive_upgrade(item, handlers, _global_coordinate_context=_global_coordinate_context) for item in data
        ]
    if not isinstance(data, dict):
        return data

    node = dict(data)
    node_type = node.get("object_type", object_type)

    rename_coordinate_system(node, node_type)
    if node_type == "Coordinate system":
        own_global_coordinate_context = _prepare_coordinate_system(node)
        own_local_coordinate_context = None
    else:
        own_global_coordinate_context = _prepare_coordinate_system(node.get("global_coordinate_system"))
        own_local_coordinate_context = _prepare_coordinate_system(node.get("local_coordinate_system"))
        if own_global_coordinate_context is None and own_local_coordinate_context is None:
            _prepare_coordinate_system(node.get("coordinate_system"))
    global_coordinate_context = own_global_coordinate_context or _global_coordinate_context
    handler = handlers.get(node_type)
    if handler is not None:
        handler(node)
    repair_described_by(node, node_type)
    repair_code_version(node, node_type)

    upgraded = {}
    for key, value in node.items():
        if key in TRANSFORM_FIELDS:
            context = global_coordinate_context
            separate_local_depth = False
            if key in {"local_axis_positions", "transform"} and own_local_coordinate_context is not None:
                context = own_local_coordinate_context
                separate_local_depth = key == "transform"
            value = _upgrade_transform_value(value, context, separate_local_depth)
        upgraded[key] = recursive_upgrade(
            value,
            handlers,
            _global_coordinate_context=global_coordinate_context,
        )
    return upgraded
