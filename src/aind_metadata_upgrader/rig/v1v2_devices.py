"""Device upgraders for rig metadata from v1 to v2."""

from aind_data_schema.components.devices import (
    Arena,
    Camera,
    CameraAssembly,
    CameraTarget,
    DAQDevice,
    Device,
    Disc,
    Detector,
    EphysAssembly,
    EphysProbe,
    FiberAssembly,
    FiberPatchCord,
    FiberProbe,
    HarpDevice,
    LaserAssembly,
    Lens,
    LickSpout,
    LickSpoutAssembly,
    Manipulator,
    Monitor,
    MotorizedStage,
    NeuropixelsBasestation,
    Olfactometer,
    Speaker,
    Treadmill,
    Tube,
    Wheel,
    DigitalMicromirrorDevice,
    PolygonalScanner,
    PockelsCell,
)
from aind_data_schema.core.instrument import (
    Connection,
    ConnectionData,
    ConnectionDirection,
)
from aind_data_schema_models.coordinates import AnatomicalRelative

from aind_metadata_upgrader.utils.v1v2_utils import (
    add_name,
    basic_device_checks,
    build_connection_from_channel,
    capitalize,
    remove,
    upgrade_filter,
    upgrade_light_source,
    upgrade_positioned_device,
    upgrade_software,
    repair_unit,
)

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

    # Create the DAQ device, or HarpDevice
    if "is_clock_generator" in device_data:
        daq_device = HarpDevice(**device_data)
    elif "bsc_firmware_version" in device_data:
        daq_device = NeuropixelsBasestation(**device_data)
    else:
        daq_device = DAQDevice(**device_data)

    return daq_device.model_dump()


def upgrade_monitor(data: dict) -> dict:
    """Upgrade Monitor device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Monitor")

    data = upgrade_positioned_device(data)

    monitor = Monitor(
        **data,
    )

    return monitor.model_dump()


def upgrade_olfactometer(data: dict) -> dict:
    """Upgrade Olfactometer device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Olfactometer")

    # Pull computer_name and create a connection if present
    if "computer_name" in data and data["computer_name"]:
        if data["computer_name"]:
            saved_connections.append(
                {
                    "receive": data["name"],
                    "send": data["computer_name"],
                }
            )
        remove(data, "computer_name")

    olfactometer = Olfactometer(
        **data,
    )

    return olfactometer.model_dump()


def upgrade_lick_spout(data: dict) -> dict:
    """Upgrade LickSpout device data from v1.x to v2.0."""

    data = basic_device_checks(data, "LickSpout")

    if "solenoid_valve" in data and data["solenoid_valve"]:
        data["solenoid_valve"] = upgrade_generic_device(data.get("solenoid_valve", {}))

    if "lick_sensor" in data and data["lick_sensor"]:
        data["lick_sensor"] = upgrade_generic_device(data.get("lick_sensor", {}))
    else:
        # The lick sensor is missing... we will add a default one and clearly mark it as unknown
        data["lick_sensor"] = Device(
            name="Unknown Lick Sensor",
        )

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

    if "stage_type" in data:
        if data["stage_type"]:
            data["motorized_stage"] = upgrade_motorized_stage(data.get("stage_type", {}))
        else:
            data["motorized_stage"] = None
    remove(data, "stage_type")

    lick_spout_assembly = LickSpoutAssembly(
        **data,
    )

    return lick_spout_assembly.model_dump()


def upgrade_speaker(data: dict) -> dict:
    """Upgrade Speaker device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Speaker")

    speaker = upgrade_positioned_device(data)

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


def upgrade_camera(data: dict) -> dict:
    """Upgrade Camera device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Camera")

    if "computer_name" in data:
        if data["computer_name"]:
            saved_connections.append(
                {
                    "send": data["name"],
                    "receive": data["computer_name"],
                }
            )
        remove(data, "computer_name")

    if "cooling" in data and not data["cooling"] or data["cooling"] == "None":
        # If someone put None it's ambiguous, but we can assume they meant no cooling
        data["cooling"] = "No cooling"

    if "bin_mode" in data and data["bin_mode"] == "None":
        data["bin_mode"] = "No binning"

    remove(data, "max_frame_rate")  # no idea when that was in v1.x

    if "recording_software" in data and data["recording_software"]:
        data["recording_software"] = upgrade_software(data.get("recording_software", {}))

    camera = Camera(
        **data,
    )

    return camera.model_dump()


def upgrade_lens(data: dict) -> dict:
    """Upgrade Lens device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Lens")

    # Remove v1 fields that are not supported in v2
    remove(data, "focal_length")
    remove(data, "focal_length_unit")
    remove(data, "lens_size_unit")
    remove(data, "max_aperture")
    remove(data, "optimized_wavelength_range")
    remove(data, "size")
    remove(data, "wavelength_unit")

    data = upgrade_generic_device(data)

    lens = Lens(
        **data,
    )

    return lens.model_dump()


CAMERA_TARGETS = {
    "body": CameraTarget.BODY,
    "side": CameraTarget.BODY,
    "bottom": CameraTarget.BODY,
    "brain": CameraTarget.BRAIN,
    "eye": CameraTarget.EYE,
    "face": CameraTarget.FACE,
    "tongue": CameraTarget.TONGUE,
    "other": CameraTarget.OTHER,
    "": CameraTarget.OTHER,
}

RELATIVE = {
    "right": AnatomicalRelative.RIGHT,
    "left": AnatomicalRelative.LEFT,
    "bottom": AnatomicalRelative.INFERIOR,
}


def parse_camera_target(target: str):
    """Separate out the strings in the target list

    Attempt to identify if any are targets and if any are anatomical relative positions
    """

    target = target.lower()

    camera_target = None

    for target_type in CAMERA_TARGETS.keys():
        if target_type in target:
            camera_target = CAMERA_TARGETS[target_type]
            break

    if not camera_target:
        raise ValueError(f"Invalid camera target: {target}. Must be one of {list(CAMERA_TARGETS.keys())}.")

    relative_positions = []

    for relative in RELATIVE.keys():
        if relative in target:
            relative_positions.append(RELATIVE[relative])

    return camera_target, relative_positions


def upgrade_camera_assembly(data: dict) -> dict:
    """Upgrade CameraAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    if "scope_assembly_name" in data and not data.get("name"):
        data["name"] = data["scope_assembly_name"]
        remove(data, "scope_assembly_name")
    data = add_name(data, "CameraAssembly")

    if "filter" in data and data["filter"]:
        data["filter"] = upgrade_filter(data.get("filter", {}))
    data["camera"] = upgrade_camera(data.get("camera", {}))
    data["lens"] = upgrade_lens(data.get("lens", {}))

    if "camera_target" not in data or not data["camera_target"]:
        if "probe" in data["camera"]["name"].lower():
            data["target"] = CameraTarget.BRAIN
            relative_positions = [AnatomicalRelative.SUPERIOR]
    else:
        data["target"], relative_positions = parse_camera_target(data.get("camera_target", ""))

    if data["target"] == CameraTarget.OTHER:
        print(data)
        raise NotImplementedError()

    remove(data, "camera_target")

    data = upgrade_positioned_device(data, relative_positions)

    camera_assembly = CameraAssembly(
        **data,
    )

    return camera_assembly.model_dump()


def upgrade_manipulator(data: dict) -> dict:
    """Upgrade Manipulator device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Manipulator")

    manipulator = Manipulator(**data)

    return manipulator.model_dump()


def upgrade_ephys_probe(data: dict) -> dict:
    """Upgrade EphysProbe device data from v1.x to v2.0."""

    data = basic_device_checks(data, "EphysProbe")

    if "lasers" in data and data["lasers"]:
        # Store lasers as a connection
        print(data)
        raise NotImplementedError("Laser needs to be saved as connection")
        # saved_connections.append(

        # )
    remove(data, "lasers")

    # Handle headstage if present
    if "headstage" in data and data["headstage"]:
        data["headstage"] = upgrade_generic_device(data["headstage"])

    ephys_probe = EphysProbe(**data)

    return ephys_probe.model_dump()


def upgrade_ephys_assembly(data: dict) -> dict:
    """Upgrade EphysAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    if "ephys_assembly_name" in data:
        data["name"] = data["ephys_assembly_name"]
        remove(data, "ephys_assembly_name")
    data = add_name(data, "EphysAssembly")

    # Upgrade the manipulator
    if "manipulator" in data:
        data["manipulator"] = upgrade_manipulator(data["manipulator"])

    # Upgrade the probes array
    if "probes" in data:
        upgraded_probes = []
        for probe in data["probes"]:
            upgraded_probes.append(upgrade_ephys_probe(probe))
        data["probes"] = upgraded_probes

    # Create EphysAssembly object
    ephys_assembly = EphysAssembly(**data)

    return ephys_assembly.model_dump()


def upgrade_fiber_assembly(data: dict) -> dict:
    """Upgrade FiberAssembly device data from v1.x to v2.0."""

    # Handle fiber_assembly_name
    if "fiber_assembly_name" in data:
        data["name"] = data["fiber_assembly_name"]
        remove(data, "fiber_assembly_name")

    # Perform basic device checks
    data = add_name(data, "FiberAssembly")

    # Upgrade the manipulator
    if "manipulator" in data and data["manipulator"]:
        data["manipulator"] = upgrade_manipulator(data["manipulator"])

    # Upgrade the fibers array to use FiberProbe
    if "fibers" in data and data["fibers"]:
        upgraded_fibers = []
        for fiber in data["fibers"]:
            upgraded_fibers.append(upgrade_fiber_probe(fiber))
        data["fibers"] = upgraded_fibers

    # Create FiberAssembly object
    fiber_assembly = FiberAssembly(**data)

    return fiber_assembly.model_dump()


def upgrade_fiber_probe(data: dict) -> dict:
    """Upgrade FiberProbe device data from v1.x to v2.0."""

    data = basic_device_checks(data, "FiberProbe")

    if "core_diameter_unit" in data and data["core_diameter_unit"]:
        data["core_diameter_unit"] = repair_unit(data["core_diameter_unit"])

    fiber_probe = FiberProbe(**data)

    return fiber_probe.model_dump()


def upgrade_detector(data: dict) -> dict:
    """Upgrade detector data to the new model."""

    data = basic_device_checks(data, "Detector")

    data = capitalize(data, "cooling")
    data = capitalize(data, "bin_mode")

    if "cooling" in data and not data["cooling"] or data["cooling"] == "None":
        data["cooling"] = "No cooling"

    if "bin_mode" in data and data["bin_mode"] == "None":
        data["bin_mode"] = "No binning"

    remove(data, "max_frame_rate")  # no idea when that was in v1.x

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


def upgrade_fiber_patch_cord(data: dict) -> dict:
    """Upgrade FiberPatchCord device data from v1.x to v2.0."""

    data = basic_device_checks(data, "FiberPatchCord")

    fiber_patch_cord = FiberPatchCord(**data)

    return fiber_patch_cord.model_dump()


def upgrade_laser_assembly(data: dict) -> dict:
    """Upgrade LaserAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    data = add_name(data, "LaserAssembly")

    # Upgrade the manipulator
    if "manipulator" in data and data["manipulator"]:
        data["manipulator"] = upgrade_manipulator(data["manipulator"])

    # Upgrade the lasers array
    if "lasers" in data and data["lasers"]:
        upgraded_lasers = []
        for laser in data["lasers"]:
            upgraded_lasers.append(upgrade_light_source(laser))
        data["lasers"] = upgraded_lasers

    # Upgrade the collimator (it's just a generic Device in v2)
    if "collimator" in data and data["collimator"]:
        data["collimator"] = upgrade_generic_device(data["collimator"])

    # Upgrade the fiber (mapped from "fiber" to "fiber" but using FiberPatchCord type)
    if "fiber" in data and data["fiber"]:
        data["fiber"] = upgrade_fiber_patch_cord(data["fiber"])

    # Create LaserAssembly object
    laser_assembly = LaserAssembly(**data)

    return laser_assembly.model_dump()


def upgrade_dmd(data: dict) -> dict:
    """Upgrade DMD device data from v1.x to v2.0."""

    data = basic_device_checks(data, "DMD")

    dmd = DigitalMicromirrorDevice(**data)

    return dmd.model_dump()


def upgrade_polygonal_scanner(data: dict) -> dict:
    """Upgrade PolygonalScanner device data from v1.x to v2.0."""

    data = basic_device_checks(data, "PolygonalScanner")

    polygonal_scanner = PolygonalScanner(**data)

    return polygonal_scanner.model_dump()


def upgrade_pockels_cell(data: dict) -> dict:
    """Upgrade PockelsCell device data from v1.x to v2.0."""

    data = basic_device_checks(data, "PockelsCell")

    pockels_cell = PockelsCell(**data)

    return pockels_cell.model_dump()
