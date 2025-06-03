"""Upgraders for specific devices from v1 to v2."""

from aind_data_schema.components.devices import (
    Enclosure,
    Objective,
    Detector,
    Camera,
    Laser,
    LightEmittingDiode,
    Lamp,
    Lens,
    MotorizedStage,
    ScanningStage,
    AdditionalImagingDevice,
    DAQDevice,
)

from aind_data_schema_models.devices import ImagingDeviceType

from aind_metadata_upgrader.utils.v1v2_utils import (
    capitalize,
    remove,
    basic_device_checks,
    build_connection_from_channel,
)

saved_connections = []


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    data = basic_device_checks(data, "Enclosure")

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    data = basic_device_checks(data, "Objective")

    objective = Objective(
        **data,
    )

    return objective.model_dump()


def upgrade_detector(data: dict) -> dict:
    """Upgrade detector data to the new model."""

    data = basic_device_checks(data, "Detector")

    data = capitalize(data, "cooling")
    data = capitalize(data, "bin_mode")

    # Save computer_name connection
    if "computer_name" in data:
        if data["computer_name"]:
            saved_connections.append(
                {
                    "send": data["name"],
                    "receive": data["computer_name"],
                }
            )
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

    data = basic_device_checks(data, "Lens")

    # Remove old Device fields and deprecated fields
    remove(data, "device_type")
    remove(data, "size")  # maps to more specific fields
    remove(data, "optimized_wavelength_range")
    remove(data, "wavelength_unit")

    lens = Lens(**data)
    return lens.model_dump()


def upgrade_motorized_stages(data: dict) -> dict:
    """Upgrade motorized stage data to the new model."""

    data = basic_device_checks(data, "Motorized stage")

    # Remove old Device fields
    remove(data, "device_type")

    stage = MotorizedStage(**data)
    return stage.model_dump()


def upgrade_scanning_stages(data: dict) -> dict:
    """Upgrade scanning stage data to the new model."""

    data = basic_device_checks(data, "Scanning stage")

    # Remove old Device fields
    remove(data, "device_type")

    stage = ScanningStage(**data)
    return stage.model_dump()


def upgrade_additional_devices(data: dict) -> dict:
    """Upgrade additional imaging device data to the new model."""

    data = basic_device_checks(data, "Additional device")

    # Remove old Device fields
    remove(data, "device_type")
    remove(data, "type")

    if "imaging_device_type" not in data:
        data["imaging_device_type"] = ImagingDeviceType.OTHER
        data["notes"] = (
            data["notes"]
            if data["notes"]
            else "" + " (v1v2 upgrade): 'imaging_device_type' field was missing, defaulting to 'Other'."
        )

    device = AdditionalImagingDevice(**data)
    return device.model_dump()


def upgrade_daq_devices(device: dict) -> dict:
    """Upgrade DAQ devices to the new model."""

    # Perform basic device upgrades
    device_data = basic_device_checks(device, "DAQ Device")

    # Remove old Device fields specific to DAQ
    remove(device_data, "device_type")

    # Handle computer_name connection if present
    if "computer_name" in device_data:
        if device_data["computer_name"]:
            saved_connections.append(
                {
                    "send": device_data["name"],
                    "receive": device_data["computer_name"],
                }
            )
        remove(device_data, "computer_name")

    # Process channels and save connections
    if "channels" in device_data:
        upgraded_channels = []
        for channel in device_data["channels"]:
            # Upgrade channel to new format
            upgraded_channel = {
                "channel_name": channel["channel_name"],
                "channel_type": channel["channel_type"],
            }

            # Keep optional fields if present
            if "port" in channel and channel["port"] is not None:
                upgraded_channel["port"] = channel["port"]
            if "channel_index" in channel and channel["channel_index"] is not None:
                upgraded_channel["channel_index"] = channel["channel_index"]
            if "sample_rate" in channel and channel["sample_rate"] is not None:
                upgraded_channel["sample_rate"] = channel["sample_rate"]
            if "sample_rate_unit" in channel and channel["sample_rate_unit"] is not None:
                upgraded_channel["sample_rate_unit"] = channel["sample_rate_unit"]
            if "event_based_sampling" in channel and channel["event_based_sampling"] is not None:
                upgraded_channel["event_based_sampling"] = channel["event_based_sampling"]

            upgraded_channels.append(upgraded_channel)

            # Save connection information based on channel type
            connection = build_connection_from_channel(channel, device_data["name"])
            saved_connections.append(connection.model_dump())

        device_data["channels"] = upgraded_channels

    # Create the DAQ device
    daq_device = DAQDevice(**device_data)

    return daq_device.model_dump()
