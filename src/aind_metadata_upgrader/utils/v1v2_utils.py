"""Shared utility functions for the AIND Metadata Upgrader."""

from aind_data_schema.components.coordinates import (
    Affine,
    CoordinateSystemLibrary,
    Scale,
    Translation,
)
from aind_data_schema.components.devices import (
    Enclosure,
    Filter,
    Lamp,
    Laser,
    LightEmittingDiode,
    Objective,
    Lens,
)
from aind_data_schema.components.identifiers import Software
from aind_data_schema.core.instrument import (
    Connection,
    ConnectionData,
    ConnectionDirection,
)
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.units import SizeUnit

MODALITY_MAP = {
    "SmartSPIM": Modality.SPIM,
}

counts = {}


def upgrade_v1_modalities(data: dict) -> list:
    """Upgrade v1.x modalities lists to the v2.0 format"""

    modalities = data.get("modality", [])

    if not isinstance(modalities, list):
        if isinstance(modalities, str):
            # Coerce single modality to it's object
            if modalities in MODALITY_MAP:
                modalities = [MODALITY_MAP[modalities].model_dump()]
            else:
                # Convert try to get a Modality object from abbreviation
                try:
                    modalities = [Modality.from_abbreviation(modalities).model_dump()]
                except Exception as e:
                    raise ValueError(f"Unsupported modality abbreviation: {modalities}") from e
        else:
            modalities = [modalities]

    return modalities


def add_name(data: dict, type: str) -> dict:
    """Add a name field if it's missing, keep track of counts in a global
    variable."""

    if "name" not in data or not data["name"]:
        global counts
        if type not in counts:
            counts[type] = 0
        counts[type] += 1
        name = f"{type} {counts[type]}"
        data["name"] = name

    return data


def repair_manufacturer(data: dict) -> dict:
    """Repair the manufacturer field to ensure it's an Organization object."""

    if "manufacturer" in data and isinstance(data["manufacturer"], str):
        # Convert string to Organization object
        data["manufacturer"] = Organization.from_name(data["manufacturer"]).model_dump()

    if "manufacturer" in data and isinstance(data["manufacturer"], dict):
        if data["manufacturer"]["name"] == "Other" and not data["notes"]:
            data["notes"] = (
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): 'manufacturer' was set to 'Other'"
                " and notes were empty, manufacturer is unknown."
            )

    if "manufacturer" not in data or not data["manufacturer"]:
        data["manufacturer"] = Organization.OTHER.model_dump()
        if "notes" in data:
            data["notes"] = (
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): 'manufacturer' field was missing, defaulting to 'Other'."
            )

    return data


def upgrade_device(data: dict) -> dict:
    """Remove old Device fields"""

    if "device_type" in data:
        del data["device_type"]
    if "path_to_cad" in data:
        del data["path_to_cad"]
    if "port_index" in data:
        del data["port_index"]
    if "daq_channel" in data:
        if data["daq_channel"]:
            raise ValueError("DAQ Channel has a value -- cannot upgrade record.")
        del data["daq_channel"]

    return data


def basic_device_checks(data: dict, type: str) -> dict:
    """Perform basic checks:

    - Check that name is set correctly or set to a default
    - Check that organization is not a string, but an Organization object
    """
    data = upgrade_device(data)
    data = add_name(data, type)
    data = repair_manufacturer(data)

    return data


def capitalize(data: dict, field: str) -> dict:
    """Capitalize the first letter of a field in the data dictionary."""

    if field in data and isinstance(data[field], str):
        data[field] = data[field].capitalize()

    return data


def remove(data: dict, field: str):
    """Remove a field from the data dictionary if it exists."""

    if field in data:
        del data[field]


def upgrade_software(data: dict | str) -> dict:
    """Upgrade software class from v1.x to v2.0"""

    if isinstance(data, str):
        return Software(
            name=data,
        ).model_dump()
    elif isinstance(data, dict):
        remove(data, "url")
        remove(data, "parameters")

        return data
    else:
        print(data)
        raise ValueError("Software data must be a string or a dictionary.")


def build_connection_from_channel(channel: dict, device_name: str) -> Connection:
    """Build a connection object from a DAQ channel."""
    if "device_name" in channel and channel["device_name"]:
        channel_type = channel.get("channel_type", "")

        if "Output" in channel_type:
            # For output channels, DAQ sends to the device
            connection = Connection(
                device_names=[device_name, channel["device_name"]],
                connection_data={
                    device_name: ConnectionData(direction=ConnectionDirection.SEND, port=channel["channel_name"]),
                    channel["device_name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE, port=channel["channel_name"]
                    ),
                },
            )
        elif "Input" in channel_type:
            # For input channels, device sends to DAQ
            connection = Connection(
                device_names=[channel["device_name"], device_name],
                connection_data={
                    channel["device_name"]: ConnectionData(
                        direction=ConnectionDirection.SEND, port=channel["channel_name"]
                    ),
                    device_name: ConnectionData(direction=ConnectionDirection.RECEIVE, port=channel["channel_name"]),
                },
            )
        else:
            # Default case - assume output
            connection = Connection(
                device_names=[device_name, channel["device_name"]],
                connection_data={
                    device_name: ConnectionData(direction=ConnectionDirection.SEND, port=channel["channel_name"]),
                    channel["device_name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE, port=channel["channel_name"]
                    ),
                },
            )

        return connection

    raise ValueError("Channel must have a 'device_name' field to build a connection.")


def upgrade_filter(data: dict) -> dict:
    """Upgrade filter data to the new model."""

    data = basic_device_checks(data, "Filter")

    # Remove old Device fields
    remove(data, "device_type")
    remove(data, "filter_wheel_index")
    remove(data, "diameter")
    remove(data, "diameter_unit")
    remove(data, "thickness")
    remove(data, "thickness_unit")
    remove(data, "cut_off_frequency")
    remove(data, "cut_off_frequency_unit")
    remove(data, "cut_on_frequency")
    remove(data, "cut_on_frequency_unit")
    remove(data, "description")
    remove(data, "height")
    remove(data, "width")
    remove(data, "size_unit")

    # Ensure filter_type is set
    if "type" in data:
        data["filter_type"] = data["type"]
        remove(data, "type")

    filter_device = Filter(**data)
    return filter_device.model_dump()


def upgrade_positioned_device(data: dict, relative_position_list: list = []) -> dict:
    """Take v1 RelativePosition object

    and convert to the new relative_position/coordinate_system/transform pattern
    """

    relative_position = data.get("position", {})
    remove(data, "position")

    if not relative_position:
        # No information about relative position, set defaults
        data["relative_position"] = relative_position_list
        data["coordinate_system"] = None
        data["transform"] = None
    else:
        transforms = relative_position.get("device_position_transforms", [])

        data["transform"] = []

        translation = None

        for transform in transforms:
            if transform["type"] == "rotation":
                # rotation data is originally stored as a flat list 3 x 3, we convert to list of lists
                data["transform"].append(
                    Affine(
                        affine_transform=[
                            transform["rotation"][0:3],
                            transform["rotation"][3:6],
                            transform["rotation"][6:9],
                        ]
                    ).model_dump()
                )
            elif transform["type"] == "translation":
                translation = Translation(translation=transform["translation"])
                data["transform"].append(translation.model_dump())
            else:
                raise ValueError(f"Unsupported transform type: {transform['type']}")

        origin = relative_position.get("device_origin", {})
        # axes = relative_position.get("device_axes", [])

        # We can't easily recover the relative position, leave this for a data migration later
        data["relative_position"] = []

        # Rather than parse the origin/axes, we'll use a library coordinate system
        if origin == "Center of Screen on Face":
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_MONITOR_RTF
        elif origin == "Located on face of the lens mounting surface in its center":
            data["coordinate_system"] = CoordinateSystemLibrary.SIPE_CAMERA_RBF
        else:
            print(relative_position)
            raise ValueError(f"Unsupported origin: {origin}")
    return data


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    data = basic_device_checks(data, "Enclosure")

    if "height" in data["size"]:
        width = data["size"].get("width", 0)
        length = data["size"].get("length", 0)
        height = data["size"].get("height", 0)
        data["size_unit"] = data["size"].get("unit", "mm")
        data["size"] = Scale(
            scale=[
                width,
                length,
                height,
            ],
        )
        data["notes"] = data["notes"] if data["notes"] else "" + " (v1v2 upgrade): Scale is width/length/height"

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_lens(data: dict) -> dict:
    """Upgrade lens data to the new model."""

    data = basic_device_checks(data, "Lens")

    # Remove old Device fields and deprecated fields
    remove(data, "size")  # maps to more specific fields
    remove(data, "optimized_wavelength_range")
    remove(data, "wavelength_unit")
    remove(data, "focal_length")
    remove(data, "focal_length_unit")
    remove(data, "lens_size_unit")
    remove(data, "max_aperture")

    lens = Lens(**data)
    return lens.model_dump()


COUPLING_MAPPING = {
    "SMF": "Single-mode fiber",
}


def upgrade_light_source(data: dict) -> dict:
    """Upgrade light source data to the new model."""

    data = basic_device_checks(data, "Light Source")

    # Handle the device_type field to determine which specific light source type
    device_type = data.get("device_type", "").lower()

    # Remove device_type as it's not needed in v2
    remove(data, "device_type")
    remove(data, "max_power")
    remove(data, "maximum_power")
    remove(data, "power_unit")
    remove(data, "item_number")

    if "coupling" in data:
        # Convert coupling to a more readable format
        data["coupling"] = COUPLING_MAPPING.get(data["coupling"], data["coupling"])

    # Old light sources have a 'type' field, which we will remove
    if "type" in data and not device_type:
        device_type = data["type"].lower()
        del data["type"]

    # Based on device_type, create the appropriate light source
    if (
        "laser" in device_type
        or ("notes" in data and data["notes"] and "laser" in data["notes"].lower())
        or ("name" in data and data["name"] and "laser" in data["name"].lower())
    ):
        light_source = Laser(**data)
    elif "led" in device_type or "light emitting diode" in device_type or "led" in data["name"].lower():
        light_source = LightEmittingDiode(**data)
    elif "lamp" in device_type:
        light_source = Lamp(**data)
    elif "Axon 920-2 TPC" in data.get("name", ""):
        light_source = Laser(**data)
    else:
        print(data)
        raise ValueError(f"Unsupported light source type: {device_type}")

    return light_source.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    data = basic_device_checks(data, "Objective")

    objective = Objective(
        **data,
    )

    return objective.model_dump()


def repair_unit(broken_unit: str) -> str:
    """Check for broken unit strings and repair them"""
    if broken_unit == "nm":
        return SizeUnit.NM.value
    elif broken_unit == "um":
        return SizeUnit.UM.value
    elif broken_unit == "mm":
        return SizeUnit.MM.value
    elif broken_unit == "cm":
        return SizeUnit.CM.value
    elif broken_unit == "m":
        return SizeUnit.M.value
    else:
        return broken_unit
