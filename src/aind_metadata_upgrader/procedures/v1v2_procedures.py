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
)

coordinate_system_required = False


def upgrade_craniotomy(data: dict) -> dict:
    """Upgrade Craniotomy procedure from V1 to V2"""
    # V1 uses craniotomy_coordinates_*, V2 uses coordinate system
    upgraded_data = data.copy()

    # Remove V1-specific fields that don't exist in V2
    v1_only_fields = ["craniotomy_coordinates_ml", "craniotomy_coordinates_ap",
                      "craniotomy_coordinates_unit", "craniotomy_coordinates_reference"]
    for field in v1_only_fields:
        upgraded_data.pop(field, None)

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


def upgrade_nanoject_injection(data: dict) -> dict:
    """Upgrade NanojectInjection procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    return BrainInjection(**upgraded_data).model_dump()


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