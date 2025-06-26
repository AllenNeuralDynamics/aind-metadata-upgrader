"""Shared utility functions for the AIND Metadata Upgrader."""

from typing import Optional
from aind_data_schema.components.measurements import (
    PowerCalibration,
    VolumeCalibration,
)

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
    Computer,
    Device,
)
from aind_data_schema.components.identifiers import Software
from aind_data_schema.core.instrument import (
    Connection,
    ConnectionData,
    ConnectionDirection,
)
from aind_data_schema.core.procedures import Procedures
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.units import SizeUnit, TimeUnit, VolumeUnit, PowerUnit
from aind_data_schema_models.brain_atlas import CCFv3

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


ORG_MAP = {
    "LiveCanvas Technologies": Organization.LIFECANVAS,
}


def repair_organization(data: str) -> dict:
    """Convert organizations passed as strings to Organization objects."""
    organization = Organization.from_name(data)
    if organization:
        return organization.model_dump()
    else:
        if data in ORG_MAP.keys():
            return ORG_MAP[data].model_dump()
        else:
            raise ValueError(f"Unsupported organization name: {data}.")


def repair_manufacturer(data: dict) -> dict:
    """Repair the manufacturer field to ensure it's an Organization object."""

    if "manufacturer" in data and isinstance(data["manufacturer"], str):
        # Convert string to Organization object
        data["manufacturer"] = repair_organization(data["manufacturer"])

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

    remove(data, "path_to_cad")
    remove(data, "port_index")

    if "device_type" in data:
        del data["device_type"]

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


def upgrade_generic_Device(data: dict) -> dict:
    """Upgrade a generic Device object"""

    # Some Devices have a device_type field, which now specifies a real object type
    device_type = data.get("device_type", "").lower()

    data = basic_device_checks(data, "Device")

    if device_type == "computer":
        return Computer(**data).model_dump()

    return Device(**data).model_dump()


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

    # For multiband filter, make the center_wavelength a list
    if data["filter_type"] == "Multiband":
        if "center_wavelength" in data and isinstance(data["center_wavelength"], (int, float)):
            data["center_wavelength"] = [data["center_wavelength"]]

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

    # Handle the device_type field to determine which specific light source type
    device_type = data.get("device_type", "").lower()

    data = basic_device_checks(data, "Light Source")

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


def upgrade_calibration(data: dict) -> Optional[dict]:
    """Pull calibration information"""

    if "Water calibration" in data.get("description", ""):
        # Water calibration, we can handle this

        # drop empty calibratoins
        if not data["input"]["valve open time (s):"] and not data["output"]["water volume (ul):"]:
            return None

        calibration = VolumeCalibration(
            calibration_date=data["calibration_date"],
            device_name=data["device_name"],
            input=data["input"]["valve open time (s):"],
            input_unit=TimeUnit.S,
            output=data["output"]["water volume (ul):"],
            output_unit=VolumeUnit.UL,
            notes=(
                data["notes"]
                if data["notes"]
                else "" + " (v1v2 upgrade): Liquid calibration upgraded from v1.x format."
            ),
        )
    elif (
        "laser power calibration" in data.get("description", "").lower()
        and "power_setting" in data.get("input", {})
        and "power_output" in data.get("output", {})
    ):
        # Laser calibration, may or may not have data

        power_setting = data["input"].get("power_setting", None)
        power_output = data["output"].get("power_output", None)

        # Drop empty calibrations
        if not power_setting and not power_output:
            return None

        calibration = PowerCalibration(
            calibration_date=data["calibration_date"],
            device_name=data["device_name"],
            input=power_setting,
            input_unit=PowerUnit.PERCENT,
            output=power_output,
            output_unit=PowerUnit.MW,
        )
    elif (
        "laser power calibration" in data.get("description", "").lower()
        and "power_setting" in data.get("input", {})
        and "power_measurement" in data.get("output", {})
    ):
        # Laser calibration, may or may not have data

        power_setting = data["input"].get("power_setting", {}).get("value", None)
        input_unit = data["input"].get("power_setting", {}).get("unit", PowerUnit.PERCENT.value)
        power_output = data["output"].get("power_measurement", {}).get("value", None)
        output_unit = data["output"].get("power_measurement", {}).get("unit", PowerUnit.MW.value)

        # Drop empty calibrations
        if not power_setting and not power_output:
            return None

        print(data)

        calibration = PowerCalibration(
            calibration_date=data["calibration_date"],
            device_name=data["device_name"],
            input=[power_setting],
            input_unit=input_unit,
            output=[power_output],
            output_unit=output_unit,
        )
    elif "laser power calibration" in data.get("description", "").lower() and "power percent" in data.get("input", {}):
        # Laser calibration, may or may not have data

        # Drop empty calibrations
        if not data["input"]["power percent"] and not data["output"]["power mW"]:
            return None

        calibration = PowerCalibration(
            calibration_date=data["calibration_date"],
            device_name=data["device_name"],
            input=data["input"]["power percent"],
            input_unit=PowerUnit.PERCENT,
            output=data["output"]["power mW"],
            output_unit=PowerUnit.MW,
        )
    elif "led calibration" in data.get("description", "").lower():
        # LED calibration, may or may not have data

        if not data["input"]["Power setting"] and not data["output"]["Power mW"]:
            return None

        calibration = PowerCalibration(
            calibration_date=data["calibration_date"],
            device_name=data["device_name"],
            input=data["input"]["Power setting"],
            input_unit=PowerUnit.PERCENT,
            output=data["output"]["Power mW"],
            output_unit=PowerUnit.MW,
        )
    else:
        raise ValueError(f"Unsupported calibration: {data}")

    return calibration.model_dump() if calibration else None


CCF_MAPPING = {"ALM": CCFv3.MO, "Primary Motor Cortex": CCFv3.MO}


def upgrade_targeted_structure(data: dict | str) -> dict:
    """Upgrade targeted structure, especially convert strings to structure objects"""

    if isinstance(data, str):
        if hasattr(CCFv3, data.upper()):
            return getattr(CCFv3, data.upper()).model_dump()
        if data in CCF_MAPPING.keys():
            return CCF_MAPPING[data].model_dump()
        else:
            raise ValueError(f"Unsupported targeted structure: {data}. " "Expected one of the CCF structures.")

    return data


def repair_instrument_id_mismatch(data: dict) -> dict:
    """Repair mismatched instrument IDs between acquisition and instrument sections"""

    modalities = data.get("data_description", {}).get("modalities", [])
    if any(modality["abbreviation"] == "SPIM" for modality in modalities):
        if "acquisition" in data and data["acquisition"] and "instrument_id" in data["acquisition"]:
            acquisition_instrument_id = data["acquisition"]["instrument_id"]
            if "instrument" in data and data["instrument"]:
                if "instrument_id" in data["instrument"]:
                    instrument_id = data["instrument"]["instrument_id"]

                    if acquisition_instrument_id != instrument_id:
                        print(
                            f"Warning: acquisition.instrument_id ({acquisition_instrument_id}) "
                            f"does not match instrument.instrument_id ({instrument_id}). "
                            "Updating acquisition.instrument_id to match."
                        )
                        data["instrument"]["instrument_id"] = acquisition_instrument_id
                else:
                    raise ValueError("instrument.instrument_id is missing while acquisition.instrument_id is present.")

    return data


def repair_missing_active_devices(data: dict) -> dict:
    """Create missing devices that are referenced in active_devices but not in instrument components"""

    if "acquisition" not in data or "instrument" not in data:
        return data

    # Collect active devices from data streams
    active_devices = []
    if data.get("acquisition") and "data_streams" in data["acquisition"]:
        for data_stream in data["acquisition"]["data_streams"]:
            active_devices.extend(data_stream["active_devices"])

    # Collect existing device names
    device_names = []
    if data.get("instrument"):
        for component in data["instrument"].get("components", []):
            device_names.append(component["name"])
    if data.get("procedures"):
        procedures = Procedures.model_validate(data["procedures"])
        device_names.extend(procedures.get_device_names())

    # Check if all active devices are in the available devices
    if not all(device in device_names for device in active_devices):
        missing_devices = set(active_devices) - set(device_names)
        # Create missing devices with default names
        for device in missing_devices:
            print(f"Warning: Active device '{device}' not found in instrument devices. Creating default device.")
            new_device = Device(
                name=device,
            )
            data["instrument"]["components"].append(new_device.model_dump())

    return data


def repair_metadata(data: dict) -> dict:
    """Repair the full metadata record, checking for common issues"""

    data = repair_instrument_id_mismatch(data)
    data = repair_missing_active_devices(data)

    return data
