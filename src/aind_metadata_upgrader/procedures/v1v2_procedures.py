"""Individual procedure upgrade functions for V1 to V2"""

from aind_data_schema.core.procedures import (
    Craniotomy,
    Headframe,
    GroundWireImplant,
    BrainInjection,
    Injection,
    SampleCollection,
    Perfusion,
    ProbeImplant,
    MyomatrixInsertion,
    CatheterImplant,
    GenericSurgeryProcedure,
    InjectionDynamics,
    InjectionProfile,
    ViralMaterial,
    NonViralMaterial,
    Anaesthetic,
)
from aind_data_schema.components.reagent import Reagent
from aind_data_schema.components.coordinates import (
    Translation,
    Rotation,
    CoordinateSystemLibrary,
)
from aind_data_schema_models.coordinates import AnatomicalRelative
from aind_data_schema_models.brain_atlas import CCFStructure
from aind_data_schema_models.units import AngleUnit
from aind_data_schema_models.organizations import Organization

from aind_metadata_upgrader.utils.v1v2_utils import remove, repair_organization

coordinate_system_required = False
implanted_devices = []
measured_coordinates = []


def upgrade_craniotomy(data: dict) -> dict:
    """Upgrade Craniotomy procedure from V1 to V2"""
    # V1 uses craniotomy_coordinates_*, V2 uses coordinate system
    upgraded_data = data.copy()
    
    remove(upgraded_data, "procedure_type")
    remove(upgraded_data, "recovery_time")
    remove(upgraded_data, "recovery_time_unit")
    
    # V1 craniotomy example:
    # {'bregma_to_lambda_distance': '4.386', 'bregma_to_lambda_unit': 'millimeter', 'craniotomy_hemisphere': None, 'craniotomy_type': '5 mm', 'dura_removed': None, 'implant_part_number': '5mm stacked coverslip', 'procedure_type': 'Craniotomy', 'protective_material': None, 'recovery_time': '10.0', 'recovery_time_unit': 'minute'}

    # V1 spec:
    # craniotomy_hemisphere: Optional[Side] = Field(default=None, title="Craniotomy hemisphere")
    # bregma_to_lambda_distance: Optional[Decimal] = Field(
    #     default=None, title="Bregma to lambda (mm)", description="Distance between bregman and lambda"
    # )
    # bregma_to_lambda_unit: SizeUnit = Field(default=SizeUnit.MM, title="Bregma to lambda unit")
    # implant_part_number: Optional[str] = Field(default=None, title="Implant part number")
    # dura_removed: Optional[bool] = Field(default=None, title="Dura removed")
    # protective_material: Optional[ProtectiveMaterial] = Field(default=None, title="Protective material")

    # V2 spec:

    # coordinate_system_name: Optional[str] = Field(default=None, title="Coordinate system name")
    # position: Optional[Union[Translation, List[AnatomicalRelative]]] = Field(default=None, title="Craniotomy position")

    # size: Optional[float] = Field(default=None, title="Craniotomy size", description="Diameter or side length")
    # size_unit: Optional[SizeUnit] = Field(default=None, title="Craniotomy size unit")

    # protective_material: Optional[ProtectiveMaterial] = Field(default=None, title="Protective material")
    # implant_part_number: Optional[str] = Field(default=None, title="Implant part number")
    # dura_removed: Optional[bool] = Field(default=None, title="Dura removed")

    if "protocol_id" in upgraded_data and protocol_id.lower() == "none":
        upgraded_data["protocol_id"] = None
    
    remove(upgraded_data, ")

    return Craniotomy(**upgraded_data).model_dump()


def upgrade_headframe(data: dict) -> dict:
    """Upgrade Headframe procedure from V1 to V2"""
    upgraded_data = data.copy()

    return Headframe(**upgraded_data).model_dump()


def upgrade_protective_material_replacement(data: dict) -> dict:
    """Upgrade ProtectiveMaterialReplacement (Ground wire) procedure from V1 to V2"""
    upgraded_data = data.copy()

    # V1 uses "Ground wire" as procedure_type, V2 uses GroundWireImplant
    upgraded_data.pop("procedure_type", None)

    return GroundWireImplant(**upgraded_data).model_dump()


def upgrade_viral_material(data: dict) -> dict:
    """Upgrade viral material"""

    if "titer" in data and data["titer"]:
        if isinstance(data["titer"], dict):
            data["titer"] = data["titer"]["$numberLong"]

    return ViralMaterial(**data).model_dump()


def upgrade_injection_materials(data: list) -> list:
    """Upgrade injection materials from V1 to V2"""
    # V1 uses a list of strings, V2 uses a list of BrainInjectionMaterial objects
    materials = []
    for material in data:
        if material["material_type"] == "Virus":
            materials.append(
                upgrade_viral_material(material)
            )
        elif material["material_type"] == "Reagent":
            materials.append(
                NonViralMaterial(**material).model_dump()
            )
        else:
            raise ValueError(
                f"Unsupported injection material type: {material['material_type']}. "
                "Expected 'Virus' or 'Reagent'."
            )
    return materials


def build_volume_injection_dynamics(data: dict) -> dict:
    """Build dynamics for injection procedures"""

    dynamics = []

    duration = data.get("injection_duration", None)
    duration_unit = data.get("injection_duration_unit", None)

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


CCF_MAPPING = {
    "ALM": CCFStructure.MO,
}


def upgrade_targeted_structure(data: dict | str) -> dict:
    """Upgrade targeted structure, especially convert strings to structure objects"""

    if isinstance(data, str):
        if hasattr(CCFStructure, data.upper()):
            return getattr(CCFStructure, data.upper()).model_dump()
        if data in CCF_MAPPING.keys():
            return CCF_MAPPING[data].model_dump()
        else:
            raise ValueError(
                f"Unsupported targeted structure: {data}. "
                "Expected one of the CCF structures."
            )

    return data


def upgrade_nanoject_injection(data: dict) -> dict:
    """Upgrade NanojectInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)
    
    # full list of fields to handle
    dynamics = build_volume_injection_dynamics(data)

    remove(data, "recovery_time")
    remove(data, "recovery_time_unit")
    remove(data, "instrument_id")

    # recovery_time gone
    # recovery_time_unit gone
    # injection_duration move into dynamics
    # injection_duration_unit move into dynamics
    # instrument_id ? what?
    # protocol_id

    # injection_coordinate_reference check against coordinate system

    ml = data.get("injection_coordinate_ml", None)
    ap = data.get("injection_coordinate_ap", None)
    depths = data.get("injection_coordinate_depth", [])
    unit = data.get("injection_coordinate_unit", None)

    # Scale millimeters to micrometers if needed
    if unit:
        if unit == "millimeter":
            ml = float(ml) * 1000
            ap = float(ap) * 1000
            depths = [float(depth) * 1000 for depth in depths]
        elif not unit == "micrometer":
            raise ValueError(f"Need more conditions to handle other kinds of units: {unit}")

    # Check reference
    reference = data.get("injection_coordinate_reference", None)
    # Check to make sure someone doesn't give us lambda or something, that would be a big problem
    if reference is not None and not reference == "Bregma":
        raise ValueError(
            f"Unsupported injection_coordinate_reference value: {reference}. "
            "Expected 'Bregma'."
        )

    if ml is not None:

        data["coordinates"] = []

        for depth in depths:

            # Create the translation object in BREGMA_ARID space
            translation = Translation(
                translation=[ap, ml, 0, depth]
            )

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


    # bregma_to_lambda distance: construct using measurements
    # bregma_to_lambda_unit: check against coordinate system

    # injection angle: move to coordinates
    # injection angle unit: move to Rotation class

    relative_position = []
    if "injection_hemisphere" in data and data["injection_hemisphere"] is not None:
        if data["injection_hemisphere"] == "Left":
            relative_position.append(AnatomicalRelative.LEFT)
        elif data["injection_hemisphere"] == "Right":
            relative_position.append(AnatomicalRelative.RIGHT)
        elif data["injection_hemisphere"] == "Midline":
            relative_position.append(AnatomicalRelative.ORIGIN)
        else:
            raise ValueError(
                f"Unsupported injection_hemisphere value: {data['injection_hemisphere']}"
            )

    injection_materials = upgrade_injection_materials(data.get("injection_materials", []))

    if len(injection_materials) == 0:
        injection_materials.append(
            ViralMaterial(
                name="(v1v2 upgrade) No injection material provided",
            )
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

    return injection.model_dump()


def upgrade_iontophoresis_injection(data: dict) -> dict:
    """Upgrade IontophoresisInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return BrainInjection(**upgraded_data).model_dump()


def upgrade_icv_injection(data: dict) -> dict:
    """Upgrade IntraCerebellarVentricleInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return BrainInjection(**upgraded_data).model_dump()


def upgrade_icm_injection(data: dict) -> dict:
    """Upgrade IntraCisternalMagnaInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return BrainInjection(**upgraded_data).model_dump()


def upgrade_retro_orbital_injection(data: dict) -> dict:
    """Upgrade RetroOrbitalInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return Injection(**upgraded_data).model_dump()


def upgrade_intraperitoneal_injection(data: dict) -> dict:
    """Upgrade IntraperitonealInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return Injection(**upgraded_data).model_dump()


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
