"""Device upgraders for rig metadata from v1 to v2."""

from aind_metadata_upgrader.utils.v1v2_utils import (
    add_name,
    remove,
    basic_device_checks,
    upgrade_software,
    build_connection_from_channel,
    upgrade_filter,
)

from aind_data_schema.components.devices import (
    Wheel,
    Disc,
    Treadmill,
    Tube,
    Arena,
    Device,
    DAQDevice,
    Monitor,
    Olfactometer,
    LickSpout,
    LickSpoutAssembly,
    Speaker,
    MotorizedStage,
    CameraAssembly,
    Camera,
    Lens,
)
from aind_data_schema.core.instrument import Connection, ConnectionData, ConnectionDirection

saved_connections = []


def upgrade_generic_device(data: dict) -> dict:
    """Upgrade Encodder object from v1.x to v2.0."""

    data = basic_device_checks(data, "Encoder")

    encoder = Device(
        **data,
    )

    return encoder.model_dump()


def upgrade_wheel(data: dict) -> dict:
    """Upgrade a Wheel object from v1.x to v2.0."""

    data = basic_device_checks(data, "Wheel")

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")

    data["encoder"] = upgrade_generic_device(data.get("encoder", {}))
    data["magnetic_brake"] = upgrade_generic_device(data.get("magnetic_brake", {}))
    data["torque_sensor"] = upgrade_generic_device(data.get("torque_sensor", {}))

    # Convert encoder_output, brake_output, and torque_output to Connection objects
    if "encoder_output" in data and data["encoder_output"]:
        encoder_output = data["encoder_output"]
        if "device_name" in encoder_output and encoder_output["device_name"]:
            connection = Connection(
                device_names=[encoder_output["device_name"], data["name"]],
                connection_data={
                    encoder_output["device_name"]: ConnectionData(
                        direction=ConnectionDirection.SEND, port=encoder_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE, port=encoder_output["channel_name"]
                    ),
                },
            )
            saved_connections.append(connection.model_dump())
        del data["encoder_output"]

    if "brake_output" in data and data["brake_output"]:
        brake_output = data["brake_output"]
        if "device_name" in brake_output and brake_output["device_name"]:
            connection = Connection(
                device_names=[brake_output["device_name"], data["name"]],
                connection_data={
                    brake_output["device_name"]: ConnectionData(
                        direction=ConnectionDirection.SEND, port=brake_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE, port=brake_output["channel_name"]
                    ),
                },
            )
            saved_connections.append(connection.model_dump())
        del data["brake_output"]

    if "torque_output" in data and data["torque_output"]:
        torque_output = data["torque_output"]
        if "device_name" in torque_output and torque_output["device_name"]:
            connection = Connection(
                device_names=[torque_output["device_name"], data["name"]],
                connection_data={
                    torque_output["device_name"]: ConnectionData(
                        direction=ConnectionDirection.SEND, port=torque_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE, port=torque_output["channel_name"]
                    ),
                },
            )
            saved_connections.append(connection.model_dump())
        del data["torque_output"]

    wheel = Wheel(
        **data,
    )

    return wheel.model_dump()


def upgrade_disc(data: dict) -> dict:
    """Upgrade a Disc object from v1.x to v2.0."""

    data = basic_device_checks(data, "Disc")

    remove(data, "date_surface_replaced")

    if "encoder_firmware" in data and data["encoder_firmware"]:
        data["encoder_firmware"] = upgrade_software(data["encoder_firmware"])

    disc = Disc(
        **data,
    )

    return disc.model_dump()


def upgrade_treadmill(data: dict) -> dict:
    """Upgrade a Treadmill object from v1.x to v2.0."""

    data = basic_device_checks(data, "Treadmill")

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")

    if "encoder" in data and data["encoder"]:
        data["encoder"] = upgrade_generic_device(data["encoder"])

    treadmill = Treadmill(
        **data,
    )

    return treadmill.model_dump()


def upgrade_tube(data: dict) -> dict:
    """Upgrade a Tube object from v1.x to v2.0."""

    data = basic_device_checks(data, "Tube")

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")

    tube = Tube(
        **data,
    )

    return tube.model_dump()


def upgrade_arena(data: dict) -> dict:
    """Upgrade an Arena object from v1.x to v2.0."""

    data = basic_device_checks(data, "Arena")

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")

    arena = Arena(
        **data,
    )

    return arena.model_dump()


def upgrade_mouse_platform(data: dict) -> dict:
    """Upgrade mouse platform data from v1.x to v2.0."""

    data = basic_device_checks(data, "Mouse platform")

    # Determine device type if not specified
    if "device_type" not in data:
        if "encoder_output" in data:
            data["device_type"] = "Wheel"
        elif "diameter" in data:
            data["device_type"] = "Tube"
        elif "encoder_firmware" in data:
            data["device_type"] = "Disc"
        else:
            print(data)
            raise ValueError("Cannot determine device type for mouse platform")

    # Delegate to appropriate upgrade function
    if data["device_type"] == "Wheel":
        return upgrade_wheel(data)
    elif data["device_type"] == "Disc":
        return upgrade_disc(data)
    elif data["device_type"] == "Treadmill":
        return upgrade_treadmill(data)
    elif data["device_type"] == "Tube":
        return upgrade_tube(data)
    elif data["device_type"] == "Arena":
        return upgrade_arena(data)
    else:
        raise ValueError(f"Unsupported mouse platform type: {data['device_type']}")


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


def upgrade_monitor(data: dict) -> dict:
    """Upgrade Monitor device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Monitor")

    monitor = Monitor(
        **data,
    )

    return monitor.model_dump()


def upgrade_olfactometer(data: dict) -> dict:
    """Upgrade Olfactometer device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Olfactometer")

    olfactometer = Olfactometer(
        **data,
    )

    return olfactometer.model_dump()


def upgrade_lick_spout(data: dict) -> dict:
    """Upgrade LickSpout device data from v1.x to v2.0."""

    data = basic_device_checks(data, "LickSpout")

    data["solenoid_valve"] = upgrade_generic_device(data.get("solenoid_valve", {}))
    data["lick_sensor"] = upgrade_generic_device(data.get("lick_sensor", {}))

    # Position data now goes in the configuration
    # [TODO: Check that we don't need this data in the acquisition?]
    remove(data, "side")
    remove(data, "spout_position")

    lick_spout = LickSpout(
        **data,
    )

    return lick_spout.model_dump()


def upgrade_motorized_stage(data: dict) -> dict:
    """Upgrade MotorizedStage device data from v1.x to v2.0."""

    data = basic_device_checks(data, "MotorizedStage")

    if "firmware" in data and data["firmware"]:
        data["firmware"] = upgrade_software(data.get("firmware", {}))

    motorized_stage = MotorizedStage(
        **data,
    )

    return motorized_stage.model_dump()


def upgrade_lick_spout_assembly(data: dict) -> dict:
    """Upgrade LickSpoutAssembly device data from v1.x to v2.0."""

    # Upgrade individual lick spouts if present
    if "reward_spouts" in data and data["reward_spouts"]:
        upgraded_spouts = []
        for spout in data["reward_spouts"]:
            upgraded_spouts.append(upgrade_lick_spout(spout))
        data["lick_spouts"] = upgraded_spouts
        remove(data, "reward_spouts")

    add_name(data, "LickSpoutAssembly")
    remove(data, "device_type")

    data["motorized_stage"] = upgrade_motorized_stage(data.get("stage_type", {}))
    remove(data, "stage_type")

    lick_spout_assembly = LickSpoutAssembly(
        **data,
    )

    return lick_spout_assembly.model_dump()


def upgrade_speaker(data: dict) -> dict:
    """Upgrade Speaker device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Speaker")

    speaker = Speaker(
        **data,
    )

    return speaker.model_dump()


def upgrade_stimulus_device(data: dict) -> dict:
    """Upgrade stimulus device data from v1.x to v2.0."""

    # Figure out which stimulus device type this is and use the appropriate upgrader
    device_type = data.get("device_type")

    if device_type == "Monitor":
        return upgrade_monitor(data)
    elif device_type == "Olfactometer":
        return upgrade_olfactometer(data)
    elif device_type == "Reward delivery":
        return upgrade_lick_spout_assembly(data)
    elif device_type == "Speaker":
        return upgrade_speaker(data)
    else:
        raise ValueError(f"Unsupported stimulus device type: {device_type}")


def upgrade_camera_assembly(data: dict) -> dict:
    """Upgrade CameraAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    data = basic_device_checks(data, "CameraAssembly")

    data["filter"] = upgrade_filter(data.get("filter", {}))

    camera_assembly = CameraAssembly(
        **data,
    )

    return camera_assembly.model_dump()