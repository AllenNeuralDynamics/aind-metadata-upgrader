"""Upgraders for injection procedures"""

from aind_data_schema.components.coordinates import (
    CoordinateSystemLibrary,
    Rotation,
    Translation,
)
from aind_data_schema.components.injection_procedures import (
    Injection,
    InjectionDynamics,
    InjectionProfile,
    NonViralMaterial,
    ViralMaterial,
)
from aind_data_schema.components.surgery_procedures import BrainInjection
from aind_data_schema_models.coordinates import AnatomicalRelative
from aind_data_schema_models.mouse_anatomy import InjectionTargets
from aind_data_schema_models.units import AngleUnit

from aind_metadata_upgrader.utils.v1v2_utils import (
    remove,
    upgrade_registry,
    upgrade_targeted_structure,
)

from aind_metadata_upgrader.procedures.v1v2_procedures import retrieve_bl_distance


def upgrade_viral_material(data: dict) -> dict:
    """Upgrade viral material"""

    if "titer" in data and data["titer"]:
        if isinstance(data["titer"], dict):
            data["titer"] = data["titer"]["$numberLong"]

    if "name" not in data or not data["name"]:
        data["name"] = "unknown"

    if "tars_identifiers" in data and data["tars_identifiers"]:
        # We need to upgrade the plasmid_tars_alias into a list of strings
        if "plasmid_tars_alias" in data["tars_identifiers"] and data["tars_identifiers"]["plasmid_tars_alias"]:
            data["tars_identifiers"]["plasmid_tars_alias"] = [data["tars_identifiers"]["plasmid_tars_alias"]]

    remove(data, "material_type")

    if "addgene_id" in data and data["addgene_id"]:
        data["addgene_id"] = upgrade_registry(data["addgene_id"])

    return ViralMaterial(**data).model_dump()


def upgrade_injection_materials(data: list) -> list:
    """Upgrade injection materials from V1 to V2"""
    # V1 uses a list of strings, V2 uses a list of BrainInjectionMaterial objects
    materials = []
    for material in data:
        if material["material_type"] == "Virus":
            materials.append(upgrade_viral_material(material))
        elif material["material_type"] == "Reagent":
            materials.append(NonViralMaterial(**material).model_dump())
        else:
            raise ValueError(
                f"Unsupported injection material type: {material['material_type']}. " "Expected 'Virus' or 'Reagent'."
            )
    return materials


def build_volume_injection_dynamics(data: dict) -> dict:
    """Build dynamics for injection procedures"""

    dynamics = []

    duration = data.get("injection_duration", None)
    duration_unit = data.get("injection_duration_unit", None)

    if "injection_volume" in data and isinstance(data["injection_volume"], str):
        # If injection_volume is a string, convert it to a list with one element
        data["injection_volume"] = [data["injection_volume"]]

    if "injection_volume" in data and not data["injection_volume"]:
        # If injection_volume is empty, replace with empty list
        data["injection_volume"] = []

    for volume in data.get("injection_volume", []):
        # All injections have duration/duration_unit
        dynamic = {
            "profile": InjectionProfile.BOLUS,  # We're going to assume all injections are bolus
        }

        dynamic["volume"] = volume
        dynamic["volume_unit"] = data.get("injection_volume_unit", None)

        dynamics.append(dynamic)

    # We don't know if duration was the entire duration or the per-injection duration,
    # so only keep it if we're sure there's only one dynamic
    if len(dynamics) == 1:
        dynamics[0]["duration"] = duration
        dynamics[0]["duration_unit"] = duration_unit

    return [InjectionDynamics(**dynamic).model_dump() for dynamic in dynamics]


def build_current_injection_dynamics(data: dict) -> dict:
    """Build dynamics for current injection procedures"""

    # All current injections have duration/duration_unit
    dynamics = {
        "profile": InjectionProfile.BOLUS,  # We're going to assume all current injections are constant
    }

    dynamics["injection_current"] = data.get("injection_current", None)
    dynamics["injection_current_unit"] = data.get("injection_current_unit", None)
    dynamics["alternating_current"] = data.get("alternating_current", None)

    return [InjectionDynamics(**dynamics).model_dump()]


def upgrade_injection_coordinates(data: dict) -> dict:
    """Pull the ml/ap/depths coordinates"""
    ml = data.get("injection_coordinate_ml", None)
    ap = data.get("injection_coordinate_ap", None)
    depths = data.get("injection_coordinate_depth", [])
    unit = data.get("injection_coordinate_unit", None)
    remove(data, "injection_coordinate_ml")
    remove(data, "injection_coordinate_ap")
    remove(data, "injection_coordinate_depth")
    remove(data, "injection_coordinate_unit")

    # Scale millimeters to micrometers if needed
    if unit:
        if unit == "micrometer":
            ml = float(ml) / 1000
            ap = float(ap) / 1000
            depths = [float(depth) / 1000 for depth in depths]
        elif not unit == "millimeter":
            raise ValueError(f"Need more conditions to handle other kinds of units: {unit}")

    if depths is not None:

        data["coordinates"] = []

        for depth in depths:

            # Create the translation object in BREGMA_ARID space
            translation = Translation(translation=[ap if ap else 0, ml if ml else 0, 0, depth])

            # Wrap translation in a list (this is to allow for chained translations or rotations, etc)
            coordinate = [translation.model_dump()]

            if "injection_angle" in data and data["injection_angle"] is not None:
                if not data["injection_angle_unit"] == "degrees":
                    raise ValueError(
                        f"Unsupported injection_angle_unit value: {data['injection_angle_unit']}. "
                        "Expected 'degrees'."
                    )

                rotation = Rotation(
                    angles=[data["injection_angle"], 0, 0],
                    angles_unit=AngleUnit.DEG,
                )

                coordinate.append(rotation.model_dump())

            data["coordinates"].append(coordinate)

    return data


def upgrade_generic_injection(data: dict) -> dict:
    """Generic upgrade code for Injection procedures, removes fields that are not needed in V2"""

    remove(data, "recovery_time")
    remove(data, "recovery_time_unit")
    remove(data, "instrument_id")

    return data


def validate_injection_coordinate_reference(data: dict) -> None:
    """Validate that injection coordinate reference is supported (Bregma only)"""
    reference = data.get("injection_coordinate_reference", None)
    if reference is not None and not reference == "Bregma":
        raise ValueError(f"Unsupported injection_coordinate_reference value: {reference}. " "Expected 'Bregma'.")


def build_relative_position_from_hemisphere(data: dict) -> list:
    """Convert injection_hemisphere to relative_position list"""
    relative_position = []
    if "injection_hemisphere" in data and data["injection_hemisphere"] is not None:
        if data["injection_hemisphere"] == "Left":
            relative_position.append(AnatomicalRelative.LEFT)
        elif data["injection_hemisphere"] == "Right":
            relative_position.append(AnatomicalRelative.RIGHT)
        elif data["injection_hemisphere"] == "Midline":
            relative_position.append(AnatomicalRelative.ORIGIN)
        else:
            raise ValueError(f"Unsupported injection_hemisphere value: {data['injection_hemisphere']}")
    return relative_position


def ensure_injection_materials_with_default(injection_materials: list) -> list:
    """Ensure injection materials list has at least one item, adding default if empty"""
    if len(injection_materials) == 0:
        injection_materials.append(
            ViralMaterial(
                name="(v1v2 upgrade) No injection material provided",
            ).model_dump()
        )
    return injection_materials


def get_targeted_structure_or_none(data: dict) -> dict | None:
    """Get targeted structure, handling None case properly"""
    targeted_structure_data = data.get("targeted_structure")
    if targeted_structure_data:
        return upgrade_targeted_structure(targeted_structure_data)
    return None


def upgrade_nanoject_injection(data: dict) -> tuple[dict, list]:
    """Upgrade NanojectInjection procedure from V1 to V2"""

    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    upgraded_data = upgrade_generic_injection(upgraded_data)

    # full list of fields to handle
    dynamics = build_volume_injection_dynamics(data)

    # Check reference
    reference = data.get("injection_coordinate_reference", None)
    # Check to make sure someone doesn't give us lambda or something, that would be a big problem
    if reference is not None and not reference == "Bregma":
        raise ValueError(f"Unsupported injection_coordinate_reference value: {reference}. " "Expected 'Bregma'.")

    data = upgrade_injection_coordinates(data)

    data, measured_coordinates = retrieve_bl_distance(data)

    relative_position = []
    if "injection_hemisphere" in data and data["injection_hemisphere"] is not None:
        if data["injection_hemisphere"] == "Left":
            relative_position.append(AnatomicalRelative.LEFT)
        elif data["injection_hemisphere"] == "Right":
            relative_position.append(AnatomicalRelative.RIGHT)
        elif data["injection_hemisphere"] == "Midline":
            relative_position.append(AnatomicalRelative.ORIGIN)
        else:
            raise ValueError(f"Unsupported injection_hemisphere value: {data['injection_hemisphere']}")

    injection_materials = upgrade_injection_materials(data.get("injection_materials", []))

    if len(injection_materials) == 0:
        injection_materials.append(
            ViralMaterial(
                name="(v1v2 upgrade) No injection material provided",
            ).model_dump()
        )

    injection = BrainInjection(
        injection_materials=injection_materials,
        targeted_structure=upgrade_targeted_structure(data.get("targeted_structure")),
        relative_position=relative_position,
        dynamics=dynamics,
        protocol_id=data.get("protocol_id", None),
        coordinate_system_name=CoordinateSystemLibrary.BREGMA_ARID.name,
        coordinates=data.get("coordinates", []),
    )

    return injection.model_dump(), measured_coordinates


def upgrade_iontophoresis_injection(data: dict) -> tuple[dict, list]:
    """Upgrade IontophoresisInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    upgraded_data = upgrade_generic_injection(upgraded_data)

    # Build dynamics for current-based injection
    dynamics = build_current_injection_dynamics(data)

    # Check reference
    reference = data.get("injection_coordinate_reference", None)
    # Check to make sure someone doesn't give us lambda or something, that would be a big problem
    if reference is not None and not reference == "Bregma":
        raise ValueError(f"Unsupported injection_coordinate_reference value: {reference}. " "Expected 'Bregma'.")

    data = upgrade_injection_coordinates(data)

    data, measured_coordinates = retrieve_bl_distance(data)

    relative_position = []
    if "injection_hemisphere" in data and data["injection_hemisphere"] is not None:
        if data["injection_hemisphere"] == "Left":
            relative_position.append(AnatomicalRelative.LEFT)
        elif data["injection_hemisphere"] == "Right":
            relative_position.append(AnatomicalRelative.RIGHT)
        elif data["injection_hemisphere"] == "Midline":
            relative_position.append(AnatomicalRelative.ORIGIN)
        else:
            raise ValueError(f"Unsupported injection_hemisphere value: {data['injection_hemisphere']}")

    injection_materials = upgrade_injection_materials(data.get("injection_materials", []))

    if len(injection_materials) == 0:
        injection_materials.append(
            ViralMaterial(
                name="(v1v2 upgrade) No injection material provided",
            ).model_dump()
        )

    targeted_structure = None
    if data.get("targeted_structure"):
        targeted_structure = upgrade_targeted_structure(data.get("targeted_structure"))

    injection = BrainInjection(
        injection_materials=injection_materials,
        targeted_structure=targeted_structure,
        relative_position=relative_position,
        dynamics=dynamics,
        protocol_id=data.get("protocol_id", None),
        coordinate_system_name=CoordinateSystemLibrary.BREGMA_ARID.name,
        coordinates=data.get("coordinates", []),
    )

    return injection.model_dump(), measured_coordinates


def upgrade_icv_injection(data: dict) -> dict:
    """Upgrade IntraCerebellarVentricleInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    raise NotImplementedError("ICV injection upgrade not implemented yet")

    return BrainInjection(**upgraded_data).model_dump()


def upgrade_icm_injection(data: dict) -> dict:
    """Upgrade IntraCisternalMagnaInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    raise NotImplementedError("ICM injection upgrade not implemented yet")

    return BrainInjection(**upgraded_data).model_dump()


def upgrade_retro_orbital_injection(data: dict) -> dict:
    """Upgrade RetroOrbitalInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    upgraded_data = upgrade_generic_injection(upgraded_data)
    injection_materials = upgrade_injection_materials(data.get("injection_materials", []))

    if len(injection_materials) == 0:
        injection_materials.append(
            ViralMaterial(
                name="(v1v2 upgrade) No injection material provided",
            ).model_dump()
        )

    upgraded_data["injection_materials"] = injection_materials

    upgraded_data["targeted_structure"] = InjectionTargets.RETRO_ORBITAL.model_dump()

    if "injection_eye" in data and data["injection_eye"]:
        if data["injection_eye"].lower() == "left":
            upgraded_data["relative_position"] = [AnatomicalRelative.LEFT]
        elif data["injection_eye"].lower() == "right":
            upgraded_data["relative_position"] = [AnatomicalRelative.RIGHT]
        else:
            raise ValueError(f"Unsupported injection_eye value: {data['injection_eye']}. Expected 'Left' or 'Right'.")
    remove(upgraded_data, "injection_eye")

    dynamics = build_volume_injection_dynamics(data)
    upgraded_data["dynamics"] = dynamics
    remove(upgraded_data, "injection_volume")
    remove(upgraded_data, "injection_volume_unit")
    remove(upgraded_data, "injection_duration")
    remove(upgraded_data, "injection_duration_unit")

    return Injection(**upgraded_data).model_dump()


def upgrade_intraperitoneal_injection(data: dict) -> dict:
    """Upgrade IntraperitonealInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return Injection(**upgraded_data).model_dump()
