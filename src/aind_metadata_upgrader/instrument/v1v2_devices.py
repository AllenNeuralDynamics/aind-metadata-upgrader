"""Upgraders for specific devices from v1 to v2."""

from aind_data_schema.components.devices import (
    Enclosure,
    Objective,
    Detector,
    Camera,
    Laser,
    LightEmittingDiode,
    Lamp,
    Filter,
    Lens,
    MotorizedStage,
    ScanningStage,
    AdditionalImagingDevice,
)

from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.devices import ImagingDeviceType

counts = {}
saved_connections = []


def capitalize(data: dict, field: str) -> dict:
    """Capitalize the first letter of a field in the data dictionary."""

    if field in data and isinstance(data[field], str):
        data[field] = data[field].capitalize()

    return data


def remove(data: dict, field: str) -> dict:
    """Remove a field from the data dictionary if it exists."""

    if field in data:
        del data[field]

    return data


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

    if data["manufacturer"]["name"] == "Other" and not data["notes"]:
        data["notes"] = (
            " (v1v2 upgrade): 'manufacturer' was set to 'Other'"
            " and notes were empty, manufacturer is unknown."
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


def basic_checks(data: dict, type: str) -> dict:
    """Perform basic checks:

    - Check that name is set correctly or set to a default
    - Check that organization is not a string, but an Organization object
    """
    data = upgrade_device(data)
    data = add_name(data, type)
    data = repair_manufacturer(data)

    return data


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    data = basic_checks(data, "Enclosure")

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    data = basic_checks(data, "Objective")

    objective = Objective(
        **data,
    )

    return objective.model_dump()


def upgrade_detector(data: dict) -> dict:
    """Upgrade detector data to the new model."""

    data = basic_checks(data, "Detector")

    data = capitalize(data, "cooling")
    data = capitalize(data, "bin_mode")

    # Save computer_name connection
    if "computer_name" in data:
        if data["computer_name"]:
            saved_connections.append({
                "send": data["name"],
                "receive": data["computer_name"],
            })
        del data["computer_name"]

    if "type" in data and data["type"] == "Camera":
        del data["type"]
        detector = Camera(**data)
    else:
        detector = Detector(**data)

    return detector.model_dump()


COUPLING_MAPPING = {
    "SMF": "Single-mode fiber",
}


def upgrade_light_source(data: dict) -> dict:
    """Upgrade light source data to the new model."""

    data = basic_checks(data, "Light Source")

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
        device_type = data["type"].capitalize()
        del data["type"]

    # Based on device_type, create the appropriate light source
    if "laser" in device_type:
        light_source = Laser(**data)
    elif "led" in device_type or "light emitting diode" in device_type:
        light_source = LightEmittingDiode(**data)
    elif "lamp" in device_type:
        light_source = Lamp(**data)
    else:
        # Default to Laser if type is unclear
        light_source = Laser(**data)

    return light_source.model_dump()


def upgrade_lenses(data: dict) -> dict:
    """Upgrade lens data to the new model."""

    data = basic_checks(data, "Lens")

    # Remove old Device fields and deprecated fields
    remove(data, "device_type")
    remove(data, "size")  # maps to more specific fields
    remove(data, "optimized_wavelength_range")
    remove(data, "wavelength_unit")

    lens = Lens(**data)
    return lens.model_dump()


def upgrade_fluorescence_filters(data: dict) -> dict:
    """Upgrade fluorescence filter data to the new model."""

    data = basic_checks(data, "Filter")

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


def upgrade_motorized_stages(data: dict) -> dict:
    """Upgrade motorized stage data to the new model."""

    data = basic_checks(data, "Motorized stage")

    # Remove old Device fields
    remove(data, "device_type")

    stage = MotorizedStage(**data)
    return stage.model_dump()


def upgrade_scanning_stages(data: dict) -> dict:
    """Upgrade scanning stage data to the new model."""

    data = basic_checks(data, "Scanning stage")

    # Remove old Device fields
    remove(data, "device_type")

    stage = ScanningStage(**data)
    return stage.model_dump()


def upgrade_additional_devices(data: dict) -> dict:
    """Upgrade additional imaging device data to the new model."""

    data = basic_checks(data, "Additional device")

    # Remove old Device fields
    remove(data, "device_type")
    remove(data, "type")

    if "imaging_device_type" not in data:
        data["imaging_device_type"] = ImagingDeviceType.OTHER
        data["notes"] = data["notes"] if data["notes"] else "" + " (v1v2 upgrade): 'imaging_device_type' field was missing, defaulting to 'Other'."

    device = AdditionalImagingDevice(**data)
    return device.model_dump()
