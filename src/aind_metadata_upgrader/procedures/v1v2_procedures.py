"""Individual procedure upgrade functions for V1 to V2"""

from aind_data_schema.core.procedures import (
    Craniotomy,
    Headframe,
    GroundWireImplant,
    SampleCollection,
    Perfusion,
    ProbeImplant,
    MyomatrixInsertion,
    CatheterImplant,
    GenericSurgeryProcedure,
    Anaesthetic,
    CraniotomyType,
)
from aind_data_schema.components.reagent import Reagent
from aind_data_schema.components.coordinates import (
    Translation,
    CoordinateSystemLibrary,
)
from aind_data_schema_models.coordinates import AnatomicalRelative, Origin
from aind_data_schema_models.units import SizeUnit

from aind_metadata_upgrader.utils.v1v2_utils import remove, repair_organization

coordinate_system_required = False
implanted_devices = []
measured_coordinates = []


CRANIO_TYPES = {
    "5 mm": CraniotomyType.CIRCLE,
    "3 mm": CraniotomyType.CIRCLE,
}


def retrieve_bl_distance(data: dict) -> dict:
    """Pull out the Bregma/Lambda distance data"""

    if "bregma_to_lambda_distance" in data and data["bregma_to_lambda_distance"]:
        # Convert bregma/lambda distance into measured_coordinates
        # Not we're in ARID so A dimension
        if Origin.BREGMA not in measured_coordinates:
            measured_coordinates.append(
                {
                    Origin.BREGMA: Translation(
                        translation=[0, 0, 0],
                    ),
                }
            )
        distance = float(data["bregma_to_lambda_distance"])
        if distance < 0:
            distance = -distance  # Ensure distance is positive
        if data["bregma_to_lambda_unit"] == SizeUnit.MM:
            distance *= 1000  # Convert to micrometers
        elif data["bregma_to_lambda_unit"] != SizeUnit.MICROMETER:
            raise ValueError(
                f"Unsupported bregma_to_lambda_unit: {data['bregma_to_lambda_unit']}. "
                "Expected 'millimeter' or 'micrometer'."
            )
        if Origin.LAMBDA in measured_coordinates:
            distance2 = -measured_coordinates[Origin.LAMBDA].translation[0]
            distance = (distance + distance2) / 2  # Average the distance if already exists
        measured_coordinates.append(
            {
                Origin.LAMBDA: Translation(
                    translation=[-distance, 0, 0, 0],
                ),
            }
        )
        remove(data, "bregma_to_lambda_distance")
        remove(data, "bregma_to_lambda_unit")

    return data


def upgrade_hemisphere_craniotomy(data: dict) -> dict:
    """Upgrade the new-style craniotomy"""
    if "craniotomy_hemisphere" in data and data["craniotomy_hemisphere"]:
        data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name
        if data["craniotomy_hemisphere"].lower() == "left":
            data["position"] = [AnatomicalRelative.LEFT]
        elif data["craniotomy_hemisphere"].lower() == "right":
            data["position"] = [AnatomicalRelative.RIGHT]
        else:
            raise ValueError(
                f"Unsupported craniotomy_hemisphere: {data['craniotomy_hemisphere']}. "
                "Expected 'Left' or 'Right'."
            )
    elif data["craniotomy_type"] == CraniotomyType.CIRCLE:
        # If craniotomy type is circle, we don't know where it is unfortunately, so we put it at the origin
        data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name
        data["position"] = [AnatomicalRelative.ORIGIN]
    remove(data, "craniotomy_hemisphere")

    return data


def upgrade_coordinate_craniotomy(data: dict) -> dict:
    """Upgrade old-style craniotomy"""
    data["position"] = []

    # Move ml/ap position into Translation object, check units
    ml = data["craniotomy_coordinates_ml"]
    ap = data["crainotomy_coordinates_ap"]
    unit = data["craniotomy_coordinates_unit"]
    reference = data["craniotomy_coordinates_reference"]
    size = data["craniotomy_size"]
    size_unit = data["craniotomy_size_unit"]
    remove(data, "craniotomy_coordinates_ml")
    remove(data, "crainotomy_coordinates_ap")
    remove(data, "craniotomy_coordinates_unit")
    remove(data, "craniotomy_coordinates_reference")
    remove(data, "craniotomy_size")
    remove(data, "craniotomy_size_unit")

    data["size"] = size
    data["size_unit"] = size_unit

    if reference != "Bregma":
        raise ValueError("Can only handle bregma-reference craniotomies")

    if unit == "millimeter":
        ml *= 1000
        ap *= 1000
    elif unit != "micrometer":
        raise ValueError(f"Need to convert from an unsupported unit: {unit}")

    # Build translation in BREGMA_ARID
    # Unfortunately there's no guarantee that they used anterior+, right+, but we have to hope for the best
    translation = Translation(
        translation=[ap, ml, 0, 0],
    )
    data["position"].append(translation)

    return data

def upgrade_craniotomy(data: dict) -> dict:
    """Upgrade Craniotomy procedure from V1 to V2"""
    # V1 uses craniotomy_coordinates_*, V2 uses coordinate system
    upgraded_data = data.copy()

    print(data)

    remove(upgraded_data, "procedure_type")
    remove(upgraded_data, "recovery_time")
    remove(upgraded_data, "recovery_time_unit")

    if upgraded_data["craniotomy_type"] not in CraniotomyType.__members__:
        # Need to conver craniotomy type
        if upgraded_data["craniotomy_type"] in CRANIO_TYPES.keys():
            if "5" in upgraded_data["craniotomy_type"]:
                upgraded_data["size"] = 5
            elif "3" in upgraded_data["craniotomy_type"]:
                upgraded_data["size"] = 3
            upgraded_data["craniotomy_type"] = CRANIO_TYPES[upgraded_data["craniotomy_type"]]
            upgraded_data["size_unit"] = SizeUnit.MM
        else:
            raise ValueError(
                f"Unsupported craniotomy_type: {upgraded_data['craniotomy_type']}. "
                "Expected one of the CraniotomyType members."
            )

    upgraded_data = retrieve_bl_distance(upgraded_data)

    if "craniotomy_hemisphere" in upgraded_data:
        upgraded_data = upgrade_hemisphere_craniotomy(upgraded_data)
    elif "craniotomy_coordinates_ml" in upgraded_data:
        upgraded_data = upgrade_coordinate_craniotomy(upgraded_data)
    else:
        print(data)
        raise ValueError("Unknown craniotomy type, unclear how to upgrade coordinate/hemisphere data")

    if "protocol_id" in upgraded_data and upgraded_data["protocol_id"].lower() == "none":
        upgraded_data["protocol_id"] = None

    return Craniotomy(**upgraded_data).model_dump()


def upgrade_headframe(data: dict) -> dict:
    """Upgrade Headframe procedure from V1 to V2"""
    upgraded_data = data.copy()

    remove(upgraded_data, "procedure_type")

    if "headframe_part_number" in upgraded_data and not upgraded_data["headframe_part_number"]:
        # If headframe part number is empty, we set it to None
        upgraded_data["headframe_part_number"] = "unknown"

    return Headframe(**upgraded_data).model_dump()


def upgrade_protective_material_replacement(data: dict) -> dict:
    """Upgrade ProtectiveMaterialReplacement (Ground wire) procedure from V1 to V2"""
    upgraded_data = data.copy()

    # V1 uses "Ground wire" as procedure_type, V2 uses GroundWireImplant
    upgraded_data.pop("procedure_type", None)

    return GroundWireImplant(**upgraded_data).model_dump()


def upgrade_sample_collection(data: dict) -> dict:
    """Upgrade SampleCollection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return SampleCollection(**upgraded_data).model_dump()


def upgrade_perfusion(data: dict) -> dict:
    """Upgrade Perfusion procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return Perfusion(**upgraded_data).model_dump()


def upgrade_fiber_implant(data: dict) -> dict:
    """Upgrade FiberImplant procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return ProbeImplant(**upgraded_data).model_dump()


def upgrade_myomatrix_insertion(data: dict) -> dict:
    """Upgrade MyomatrixInsertion procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return MyomatrixInsertion(**upgraded_data).model_dump()


def upgrade_catheter_implant(data: dict) -> dict:
    """Upgrade CatheterImplant procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return CatheterImplant(**upgraded_data).model_dump()


def upgrade_other_subject_procedure(data: dict) -> dict:
    """Upgrade OtherSubjectProcedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return GenericSurgeryProcedure(**upgraded_data).model_dump()


def upgrade_reagent(data: dict) -> dict:
    """Upgrade reagents from V1 to V2"""
    upgraded_data = data.copy()

    if "source" in upgraded_data and upgraded_data["source"] and isinstance(upgraded_data["source"], str):
        # Convert source to organization
        upgraded_data["source"] = repair_organization(upgraded_data["source"])

    return Reagent(**upgraded_data).model_dump()


def upgrade_anaesthetic(data: dict) -> dict:
    """Upgrade anesthetic from V1 to V2"""
    upgraded_data = data.copy()

    upgraded_data["anaesthetic_type"] = upgraded_data.get("type", "Unknown")
    remove(upgraded_data, "type")

    return Anaesthetic(**upgraded_data).model_dump()


def repair_generic_surgery_procedure(data: dict, subject_id: str) -> dict:
    """Upgrade GenericSurgeryProcedure from V1 to V2"""
    upgraded_data = data.copy()

    if "specimen_id" in upgraded_data and subject_id not in upgraded_data["specimen_id"]:
        # Ensure specimen_id is prefixed with subject_id
        upgraded_data["specimen_id"] = f"{subject_id}_{upgraded_data['specimen_id']}"

    return upgraded_data
