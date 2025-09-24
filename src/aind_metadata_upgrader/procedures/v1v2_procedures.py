"""Individual procedure upgrade functions for V1 to V2"""

from aind_data_schema.components.configs import ProbeConfig
from aind_data_schema.components.coordinates import (
    CoordinateSystemLibrary,
    Rotation,
    Translation,
)
from aind_data_schema.components.reagent import (
    ProteinProbe,
    ProbeReagent,
    FluorescentStain,
    StainType,
    Fluorophore,
    FluorophoreType,
)
from aind_data_schema.components.specimen_procedures import (
    HCRSeries,
    PlanarSectioning,
    Section,
    SectionOrientation,
)
from aind_data_schema.components.subject_procedures import (
    Anaesthetic,
    CatheterImplant,
    Craniotomy,
    GenericSurgeryProcedure,
    Headframe,
    MyomatrixInsertion,
    Perfusion,
    ProbeImplant,
    SampleCollection,
    WaterRestriction,
    TrainingProtocol,
    GenericSubjectProcedure,
)
from aind_data_schema.components.surgery_procedures import (
    CraniotomyType,
    GroundWireImplant,
)
from aind_data_schema_models.brain_atlas import CCFv3
from aind_data_schema_models.coordinates import AnatomicalRelative, Origin
from aind_data_schema_models.units import SizeUnit
from aind_data_schema_models.species import Species
from aind_data_schema_models.pid_names import PIDName
from aind_data_schema_models.registries import Registry
from aind_data_schema_models.organizations import Organization

from aind_metadata_upgrader.rig.v1v2_devices import upgrade_fiber_probe
from aind_metadata_upgrader.utils.v1v2_utils import remove

coordinate_system_required = False


def retrieve_bl_distance(data: dict) -> dict:
    """Pull out the Bregma/Lambda distance data"""
    measured_coordinates = []

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
        if data["bregma_to_lambda_unit"] == SizeUnit.UM:
            distance /= 1000  # Convert to micrometers
        elif data["bregma_to_lambda_unit"] != SizeUnit.MM:
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

    return data, measured_coordinates


def upgrade_hemisphere_craniotomy(data: dict) -> dict:
    """Upgrade the new-style craniotomy"""

    remove(data, "craniotomy_coordinates_ml")
    remove(data, "craniotomy_coordinates_ap")
    remove(data, "craniotomy_coordinates_unit")
    remove(data, "craniotomy_coordinates_reference")
    remove(data, "craniotomy_size")
    remove(data, "craniotomy_size_unit")

    if "craniotomy_hemisphere" in data and data["craniotomy_hemisphere"]:
        data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name
        if data["craniotomy_hemisphere"].lower() == "left":
            data["position"] = [AnatomicalRelative.LEFT]
        elif data["craniotomy_hemisphere"].lower() == "right":
            data["position"] = [AnatomicalRelative.RIGHT]
        else:
            raise ValueError(
                f"Unsupported craniotomy_hemisphere: {data['craniotomy_hemisphere']}. " "Expected 'Left' or 'Right'."
            )
    elif data["craniotomy_type"] == CraniotomyType.CIRCLE:
        # If craniotomy type is circle, we don't know where it is unfortunately, so we put it at the origin
        data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name
        data["position"] = [AnatomicalRelative.ORIGIN]
    else:
        # We don't know the hemisphere, so we put position at origin unfortunately
        data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name
        data["position"] = [AnatomicalRelative.ORIGIN]
    remove(data, "craniotomy_hemisphere")

    return data


def upgrade_coordinate_craniotomy(data: dict) -> dict:
    """Upgrade old-style craniotomy"""
    global coordinate_system_required
    coordinate_system_required = True

    # Move ml/ap position into Translation object, check units
    ml = float(data["craniotomy_coordinates_ml"])
    ap = float(data["craniotomy_coordinates_ap"])
    unit = data["craniotomy_coordinates_unit"]
    reference = data["craniotomy_coordinates_reference"]
    size = data["craniotomy_size"]
    size_unit = data["craniotomy_size_unit"]
    remove(data, "craniotomy_coordinates_ml")
    remove(data, "craniotomy_coordinates_ap")
    remove(data, "craniotomy_coordinates_unit")
    remove(data, "craniotomy_coordinates_reference")
    remove(data, "craniotomy_size")
    remove(data, "craniotomy_size_unit")

    data["size"] = size
    data["size_unit"] = size_unit

    if reference != "Bregma":
        raise ValueError("Can only handle bregma-reference craniotomies")

    if unit == "micrometer":
        ml /= 1000
        ap /= 1000
    elif unit != "millimeter":
        raise ValueError(f"Need to convert from an unsupported unit: {unit}")

    if "craniotomy_hemisphere" in data:
        # If hemisphere is available, make sure ML matches the hemisphere
        if data["craniotomy_hemisphere"].lower() == "left":
            if ml > 0:
                ml = -ml
        elif data["craniotomy_hemisphere"].lower() == "right":
            if ml < 0:
                ml = -ml
        remove(data, "craniotomy_hemisphere")

    # Build translation in BREGMA_ARID
    # Unfortunately there's no guarantee that they used anterior+, right+, but we have to hope for the best
    translation = Translation(
        translation=[ap, ml, 0, 0],
    )
    data["position"] = translation.model_dump()
    data["coordinate_system_name"] = CoordinateSystemLibrary.BREGMA_ARID.name

    return data


CRANIO_TYPES = {
    "5 mm": CraniotomyType.CIRCLE,
    "3 mm": CraniotomyType.CIRCLE,
}


def upgrade_craniotomy(data: dict) -> dict:
    """Upgrade Craniotomy procedure from V1 to V2"""
    # V1 uses craniotomy_coordinates_*, V2 uses coordinate system
    upgraded_data = data.copy()

    remove(upgraded_data, "procedure_type")
    remove(upgraded_data, "recovery_time")
    remove(upgraded_data, "recovery_time_unit")

    if upgraded_data["craniotomy_type"] not in CraniotomyType:
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

    upgraded_data, measured_coordinates = retrieve_bl_distance(upgraded_data)

    if "craniotomy_coordinates_ml" in upgraded_data and upgraded_data["craniotomy_coordinates_ml"]:
        upgraded_data = upgrade_coordinate_craniotomy(upgraded_data)
    elif "craniotomy_hemisphere" in upgraded_data:
        upgraded_data = upgrade_hemisphere_craniotomy(upgraded_data)
    else:
        raise ValueError("Unknown craniotomy type, unclear how to upgrade coordinate/hemisphere data")

    if (
        "protocol_id" in upgraded_data
        and upgraded_data["protocol_id"]
        and upgraded_data["protocol_id"].lower() == "none"
    ):
        upgraded_data["protocol_id"] = None

    try:
        return Craniotomy(**upgraded_data).model_dump(), measured_coordinates
    except Exception as e:
        print(data)
        raise e


def upgrade_headframe(data: dict) -> dict:
    """Upgrade Headframe procedure from V1 to V2"""
    upgraded_data = data.copy()

    remove(upgraded_data, "procedure_type")

    if "headframe_part_number" in upgraded_data and not upgraded_data["headframe_part_number"]:
        upgraded_data["headframe_part_number"] = "unknown"

    if "headframe_type" in upgraded_data and not upgraded_data["headframe_type"]:
        upgraded_data["headframe_type"] = "unknown"

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


def retrieve_probe_config(data: dict) -> tuple:
    """Get the Probe object and the ProbeConfig object from a ProbeImplant dict"""

    # Pull probes and move these to implanted_devices
    probe_implants = data.pop("probes", [])

    probes = []
    configs = []

    for implant in probe_implants:
        # Upgrade the probe device, if it exists
        if "ophys_probe" in implant:
            probe = implant["ophys_probe"]
            probe = upgrade_fiber_probe(probe)
            name = probe["name"]

            probes.append(probe)
        else:
            name = "unknown"

        # Upgrade the ProbeConfig
        targeted_structure = implant.get("targeted_structure", {})
        if not targeted_structure:
            targeted_structure = CCFv3.ROOT.model_dump()  # Default to ROOT if no structure provided

        ap = implant.get("stereotactic_coordinate_ap", None)
        ml = implant.get("stereotactic_coordinate_ml", None)
        dv = implant.get("stereotactic_coordinate_dv", None)

        # We don't really know which direction ap/ml/dv go...

        stereotactic_coordinate_unit = implant.get("stereotactic_coordinate_unit", "unknown")

        if stereotactic_coordinate_unit == "micrometer":
            ap = float(ap) / 1000 if ap else None
            ml = float(ml) / 1000 if ml else None
            dv = float(dv) / 1000 if dv else None
        elif stereotactic_coordinate_unit != "millimeter":
            raise ValueError(
                f"Unsupported stereotactic_coordinate_unit: {stereotactic_coordinate_unit}. "
                "Expected 'millimeter' or 'micrometer'."
            )

        stereotactic_coordinate_reference = implant.get("stereotactic_coordinate_reference", "Bregma")
        if not stereotactic_coordinate_reference:
            stereotactic_coordinate_reference = "Bregma"

        if stereotactic_coordinate_reference != "Bregma":
            raise ValueError(
                f"Unsupported stereotactic_coordinate_reference: {stereotactic_coordinate_reference}. "
                "Expected 'Bregma'."
            )

        angle = implant.get("angle", None)
        angle_unit = implant.get("angle_unit", "degrees")

        transforms = [Translation(translation=[ap, ml, 0, dv])]

        if angle:
            if angle_unit != "degrees":
                raise ValueError(f"Unsupported angle_unit: {angle_unit}. " "Expected 'degrees'.")
            rotation = Rotation(
                angles=[float(angle), 0, 0, 0],
            )
            transforms.append(rotation)

        config = ProbeConfig(
            device_name=name,
            primary_targeted_structure=targeted_structure,
            coordinate_system=CoordinateSystemLibrary.MPM_MANIP_RFB,
            transform=transforms,
        )

        configs.append(config.model_dump())

        implant = retrieve_bl_distance(implant)

    return probes, configs


def upgrade_fiber_implant(data: dict) -> list:
    """Upgrade FiberImplant procedure from V1 to V2"""
    upgraded_data = data.copy()
    upgraded_data.pop("procedure_type", None)

    probes, configs = retrieve_probe_config(upgraded_data)

    implants = []
    for i, probe in enumerate(probes):
        implants.append(
            ProbeImplant(
                protocol_id=data.get("protocol_id", "unknown"),
                implanted_device=probe,
                device_config=configs[i],
            ).model_dump()
        )

    return implants


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


def upgrade_anaesthetic(data: dict) -> dict:
    """Upgrade anaesthetic from V1 to V2"""
    upgraded_data = data.copy()

    upgraded_data["anaesthetic_type"] = upgraded_data.get("type", "Unknown")
    remove(upgraded_data, "type")

    if "duration" not in upgraded_data or upgraded_data["duration"] is None:
        upgraded_data["duration"] = 0

    return Anaesthetic(**upgraded_data).model_dump()


def repair_generic_surgery_procedure(data: dict, subject_id: str) -> dict:
    """Upgrade GenericSurgeryProcedure from V1 to V2"""
    upgraded_data = data.copy()

    if "specimen_id" in upgraded_data and subject_id not in upgraded_data["specimen_id"]:
        # Ensure specimen_id is prefixed with subject_id
        upgraded_data["specimen_id"] = f"{subject_id}_{upgraded_data['specimen_id']}"

    return upgraded_data


def upgrade_antibody(data: dict) -> dict:
    """Upgrade antibodies from V1 to V2"""
    upgraded_data = data.copy()

    if "immunolabel_class" in upgraded_data:
        if upgraded_data["immunolabel_class"].lower() == "primary":
            # Upgrade to ProbeReagent pattern
            if upgraded_data["rrid"]["name"] == "Chicken polyclonal to GFP":
                target = ProteinProbe(
                    protein=PIDName(name="GFP", registry=Registry.UNIPROT, registry_identifier="P42212"),
                    mass=float(upgraded_data.get("mass", 0)),
                    mass_unit=upgraded_data.get("mass_unit"),
                    species=Species.CHICKEN,
                )
            return ProbeReagent(
                target=target,
                name="Chicken polyclonal to GFP",
                source=Organization.from_name(upgraded_data["source"]["name"]),
                rrid=PIDName(name="Chicken polyclonal to GFP", registry=Registry.RRID, registry_identifier="ab13970"),
            ).model_dump()
        elif upgraded_data["immunolabel_class"].lower() == "secondary":
            # Upgrade to FluorescentStain
            # Example data: {
            #   'name': 'Alexa Fluor 488 goat anti-chicken IgY (H+L)',
            #   'source': {'name': 'Thermo Fisher Scientific', 'abbreviation': None,
            #              'registry': {'name': 'Research Organization Registry', 'abbreviation': 'ROR'},
            #              'registry_identifier': '03x1ewr52'},
            #   'rrid': {'name': 'Alexa Fluor 488 goat anti-chicken IgY (H+L)', 'abbreviation': None,
            #            'registry': {'name': 'Research Resource Identifiers', 'abbreviation': 'RRID'},
            #            'registry_identifier': 'A11039'},
            #   'lot_number': '2420700', 'expiration_date': None, 'immunolabel_class': 'Secondary',
            #   'fluorophore': 'Alexa Fluor 488', 'mass': '4', 'mass_unit': 'microgram', 'notes': None
            # }

            if upgraded_data["rrid"]["name"] == "Alexa Fluor 488 goat anti-chicken IgY (H+L)":
                probe = ProteinProbe(
                    protein=PIDName(name="TODO", registry=Registry.UNIPROT, registry_identifier="unknown"),
                    mass=4,
                    mass_unit="microgram",
                    species=Species.CHICKEN,
                )

                fluorophore = Fluorophore(
                    fluorophore_type=FluorophoreType.ALEXA,
                    excitation_wavelength=488,
                    excitation_wavelength_unit=SizeUnit.NM,
                )

                return FluorescentStain(
                    name=upgraded_data["rrid"]["name"],
                    source=Organization.from_name(upgraded_data["source"]["name"]),
                    probe=probe,
                    stain_type=StainType.PROTEIN,
                    fluorophore=fluorophore,
                ).model_dump()
        else:
            print(data)
            raise NotImplementedError("TODO")

    print(data)
    raise NotImplementedError("TODO")
    # Notes:
    # Primary -> ProbeReagent
    # Secondary -> FluorescentStain

    # Antibodies previously had names like "Goat anti chicken IGy" and these would need to be parsed


def upgrade_hcr_series(data: dict) -> dict:
    """Upgrade HCRSeries from V1 to V2"""
    upgraded_data = data.copy()

    return HCRSeries(**upgraded_data).model_dump()


def _create_section(
    index: int,
    specimen_id: str,
    section_distance_from_reference: float,
    section_thickness: float,
    section_thickness_unit: SizeUnit,
    section_orientation: SectionOrientation,
    section_strategy: str,
    targeted_structure,  # Remove type annotation to match usage
    coordinate_system_name: str,
) -> Section:
    """Create a single Section object for planar sectioning."""
    # Calculate the position of this slice
    slice_position = section_distance_from_reference + (index * section_thickness)

    # Create start and end coordinates based on orientation
    if section_orientation == SectionOrientation.CORONAL:
        # Coronal sections: varying anterior-posterior (A) coordinate
        start_coord = Translation(translation=[slice_position, 0, 0])
        end_coord = Translation(translation=[slice_position + section_thickness, 0, 0])
    elif section_orientation == SectionOrientation.SAGITTAL:
        # Sagittal sections: varying medial-lateral (R) coordinate
        start_coord = Translation(translation=[0, slice_position, 0])
        end_coord = Translation(translation=[0, slice_position + section_thickness, 0])
    elif section_orientation == SectionOrientation.TRANSVERSE:
        # Transverse sections: varying dorsal-ventral (I) coordinate
        start_coord = Translation(translation=[0, 0, slice_position])
        end_coord = Translation(translation=[0, 0, slice_position + section_thickness])
    else:
        raise ValueError(f"Unsupported section_orientation: {section_orientation}")

    # Handle partial slice based on section strategy
    partial_slice = None
    if section_strategy == "Hemi brain":
        partial_slice = [AnatomicalRelative.LEFT]  # Using LEFT instead of OTHER
    # For "Whole brain" or other strategies, leave partial_slice as None (empty list)

    return Section(
        output_specimen_id=specimen_id,
        targeted_structure=targeted_structure,
        coordinate_system_name=coordinate_system_name,
        start_coordinate=start_coord,
        end_coordinate=end_coord,
        thickness=section_thickness,
        thickness_unit=section_thickness_unit,
        partial_slice=partial_slice,
    )


def upgrade_planar_sectioning(data: dict) -> dict:
    """Upgrade Sectioning from V1 to V2 PlanarSectioning"""
    upgraded_data = {}

    # Remove procedure_type
    remove(data, "procedure_type")

    # Extract basic info
    number_of_slices = data["number_of_slices"]
    output_specimen_ids = data["output_specimen_ids"]
    section_orientation = data["section_orientation"]
    section_thickness = float(data["section_thickness"])
    section_thickness_unit = data["section_thickness_unit"]
    section_distance_from_reference = float(data["section_distance_from_reference"])
    section_distance_unit = data["section_distance_unit"]
    section_strategy = data.get("section_strategy", "Whole brain")
    targeted_structure = data.get("targeted_structure")

    # Validate that output_specimen_ids matches number_of_slices
    if len(output_specimen_ids) != number_of_slices:
        raise ValueError(
            f"Number of output_specimen_ids ({len(output_specimen_ids)}) "
            f"must match number_of_slices ({number_of_slices})"
        )

    # Convert units to mm if needed
    if section_thickness_unit == SizeUnit.UM:
        section_thickness /= 1000
        section_thickness_unit = SizeUnit.MM
    elif section_thickness_unit != SizeUnit.MM:
        raise ValueError(f"Unsupported section_thickness_unit: {section_thickness_unit}")

    if section_distance_unit == SizeUnit.UM:
        section_distance_from_reference /= 1000
    elif section_distance_unit != SizeUnit.MM:
        raise ValueError(f"Unsupported section_distance_unit: {section_distance_unit}")

    # Set up coordinate system - always BREGMA_ARID
    coordinate_system_name = CoordinateSystemLibrary.BREGMA_ARID.name

    # Calculate section coordinates based on orientation
    sections = []

    for i, specimen_id in enumerate(output_specimen_ids):
        section = _create_section(
            index=i,
            specimen_id=specimen_id,
            section_distance_from_reference=section_distance_from_reference,
            section_thickness=section_thickness,
            section_thickness_unit=section_thickness_unit,
            section_orientation=section_orientation,
            section_strategy=section_strategy,
            targeted_structure=targeted_structure,
            coordinate_system_name=coordinate_system_name,
        )

        sections.append(section)

    # Build the PlanarSectioning object
    upgraded_data = {
        "sections": [section.model_dump() for section in sections],
        "section_orientation": section_orientation,
    }

    return PlanarSectioning(**upgraded_data).model_dump()


def upgrade_water_restriction(data: dict) -> dict:
    """Upgrade WaterRestriction from V1 to V2"""
    remove(data, "procedure_type")
    data["ethics_review_id"] = data.get("iacuc_protocol", "unknown")
    remove(data, "iacuc_protocol")
    if not data["baseline_weight"]:
        # If baseline_weight is not provided, set it to 0
        data["baseline_weight"] = 0.0
    return WaterRestriction(
        **data,
    ).model_dump()


def upgrade_training_protocol(data: dict) -> dict:
    """Upgrade TrainingProtocol"""
    remove(data, "procedure_type")
    data["ethics_review_id"] = data.get("iacuc_protocol", "unknown")
    remove(data, "iacuc_protocol")
    return TrainingProtocol(
        **data,
    ).model_dump()


def upgrade_generic_subject_procedure(data: dict) -> dict:
    """Upgrade GenericSubjectProcedure from V1 to V2"""
    # Convert protocol_id from list to string (V1 has it as list, V2 as string)
    protocol_id = data.get("protocol_id", None)
    if isinstance(protocol_id, str) and protocol_id.lower() == "none":
        protocol_id = None

    generic_subject_procedure = GenericSubjectProcedure(
        start_date=data.get("start_date"),
        experimenters=data.get("experimenters", []),
        ethics_review_id=data.get("iacuc_protocol", "unknown"),
        protocol_id=protocol_id,
        description=data.get("description", ""),
        notes=data.get("notes"),
    )

    return generic_subject_procedure.model_dump()
