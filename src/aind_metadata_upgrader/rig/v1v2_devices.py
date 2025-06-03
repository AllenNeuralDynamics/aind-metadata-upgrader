"""Device upgraders for rig metadata from v1 to v2."""

from aind_metadata_upgrader.utils.v1v2_utils import remove, basic_device_checks, upgrade_software

from aind_data_schema.components.devices import Wheel, Disc, Treadmill, Tube, Arena, Device
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
                        direction=ConnectionDirection.SEND,
                        port=encoder_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE,
                        port=encoder_output["channel_name"]
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
                        direction=ConnectionDirection.SEND,
                        port=brake_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE,
                        port=brake_output["channel_name"]
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
                        direction=ConnectionDirection.SEND,
                        port=torque_output["channel_name"]
                    ),
                    data["name"]: ConnectionData(
                        direction=ConnectionDirection.RECEIVE,
                        port=torque_output["channel_name"]
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
