"""Device upgraders for rig metadata from v1 to v2."""

from aind_data_schema.components.devices import (
    Arena,
    Camera,
    CameraAssembly,
    CameraTarget,
    DAQDevice,
    Detector,
    Device,
    DigitalMicromirrorDevice,
    Disc,
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
    OpenEphysAcquisitionBoard,
    Olfactometer,
    PockelsCell,
    PolygonalScanner,
    Speaker,
    Treadmill,
    Tube,
    Wheel,
)
from aind_data_schema.components.connections import (
    Connection,
)
from aind_data_schema_models.coordinates import AnatomicalRelative

from aind_metadata_upgrader.utils.v1v2_utils import (
    add_name,
    basic_device_checks,
    build_connection_from_channel,
    capitalize,
    remove,
    repair_unit,
    upgrade_filter,
    upgrade_light_source,
    upgrade_positioned_device,
    upgrade_software,
    validate_frequency_unit,
)


def upgrade_generic_device_with_name(data: dict, name: str) -> dict:
    """Upgrade a named object from v1.x to v2.0."""

    data = basic_device_checks(data, name)

    device = Device(
        **data,
    )

    return device.model_dump()


def upgrade_wheel(data: dict) -> tuple[dict, list]:
    """Upgrade a Wheel object from v1.x to v2.0."""

    data = basic_device_checks(data, "Wheel")
    connections = []

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")

    data["encoder"] = upgrade_generic_device_with_name(data.get("encoder", {}), "Encoder")
    data["magnetic_brake"] = upgrade_generic_device_with_name(data.get("magnetic_brake", {}), "Magnetic brake")
    data["torque_sensor"] = upgrade_generic_device_with_name(data.get("torque_sensor", {}), "Torque sensor")

    # Convert encoder_output, brake_output, and torque_output to Connection objects
    if "encoder_output" in data and data["encoder_output"]:
        encoder_output = data["encoder_output"]
        if "device_name" in encoder_output and encoder_output["device_name"]:
            connection = Connection(
                source_device=encoder_output["device_name"],
                source_port=encoder_output["channel_name"],
                target_device=data["name"],
                target_port=encoder_output["channel_name"],
            )
            connections.append(connection.model_dump())
    remove(data, "encoder_output")

    if "brake_output" in data and data["brake_output"]:
        brake_output = data["brake_output"]
        if "device_name" in brake_output and brake_output["device_name"]:
            connection = Connection(
                source_device=brake_output["device_name"],
                source_port=brake_output["channel_name"],
                target_device=data["name"],
                target_port=brake_output["channel_name"],
            )
            connections.append(connection.model_dump())
    remove(data, "brake_output")

    if "torque_output" in data and data["torque_output"]:
        torque_output = data["torque_output"]
        if "device_name" in torque_output and torque_output["device_name"]:
            connection = Connection(
                source_device=torque_output["device_name"],
                source_port=torque_output["channel_name"],
                target_device=data["name"],
                target_port=torque_output["channel_name"],
            )
            connections.append(connection.model_dump())
    remove(data, "torque_output")

    wheel = Wheel(
        **data,
    )

    return wheel.model_dump(), connections


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
        data["encoder"] = upgrade_generic_device_with_name(data["encoder"], "Encoder")

    treadmill = Treadmill(
        **data,
    )

    return treadmill.model_dump()


def upgrade_tube(data: dict) -> dict:
    """Upgrade a Tube object from v1.x to v2.0."""

    data = basic_device_checks(data, "Tube")

    remove(data, "date_surface_replaced")
    remove(data, "surface_material")
    remove(data, "platform_type")

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


def _determine_platform_device_type(data: dict) -> str:
    """Determine the device type for mouse platform"""
    if "device_type" in data:
        return data["device_type"]

    if "platform_type" in data and data["platform_type"]:
        data["device_type"] = data["platform_type"]
        remove(data, "platform_type")
        return data["device_type"]
    elif "encoder_output" in data:
        return "Wheel"
    elif "diameter" in data:
        return "Tube"
    elif "encoder_firmware" in data:
        return "Disc"
    elif "radius" in data and "radius_unit" in data:
        return "Disc"
    else:
        print(data)
        raise ValueError("Cannot determine device type for mouse platform")


def _upgrade_platform_by_type(data: dict, device_type: str) -> tuple[dict, list]:
    """Upgrade platform based on its device type"""
    if device_type == "Wheel":
        return upgrade_wheel(data)
    elif device_type == "Disc":
        return upgrade_disc(data), []
    elif device_type == "Treadmill":
        return upgrade_treadmill(data), []
    elif device_type == "Tube":
        return upgrade_tube(data), []
    elif device_type == "Arena":
        return upgrade_arena(data), []
    else:
        raise ValueError(f"Unsupported mouse platform type: {device_type}")


def upgrade_mouse_platform(data: dict) -> tuple[dict, list]:
    """Upgrade mouse platform data from v1.x to v2.0."""

    data = basic_device_checks(data, "Mouse platform")

    # Determine device type if not specified
    device_type = _determine_platform_device_type(data)
    data["device_type"] = device_type

    # Delegate to appropriate upgrade function
    return _upgrade_platform_by_type(data, device_type)


def upgrade_daq_channels(device_data: dict) -> tuple[list, list]:
    """Upgrade DAQ device channels and save connection information."""
    upgraded_channels = []
    connections = []

    if "channels" in device_data:
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
                upgraded_channel["sample_rate_unit"] = validate_frequency_unit(channel["sample_rate_unit"])
            if "event_based_sampling" in channel and channel["event_based_sampling"] is not None:
                upgraded_channel["event_based_sampling"] = channel["event_based_sampling"]

            upgraded_channels.append(upgraded_channel)

            # Save connection information based on channel type
            connection = build_connection_from_channel(channel, device_data["name"])
            connections.append(connection.model_dump())

    # Drop duplicate channel dictionaries
    seen_channels = set()
    upgraded_channels = [
        channel
        for channel in upgraded_channels
        if tuple(channel.items()) not in seen_channels and not seen_channels.add(tuple(channel.items()))
    ]

    return upgraded_channels, connections


def upgrade_daq_devices(device: dict) -> tuple[dict, list]:
    """Upgrade DAQ devices to the new model."""

    # Perform basic device upgrades
    device_data = basic_device_checks(device, "DAQ Device")
    connections = []

    # Remove old Device fields specific to DAQ
    device_type = device_data.get("device_type")

    # Handle computer_name connection if present
    if "computer_name" in device_data:
        if device_data["computer_name"]:
            connections.append(
                {
                    "send": device_data["name"],
                    "receive": device_data["computer_name"],
                }
            )
        remove(device_data, "computer_name")

    # Process channels and save connections
    device_data["channels"], channel_connections = upgrade_daq_channels(device_data)
    connections.extend(channel_connections)

    # Create the DAQ device, or HarpDevice
    if device_type == "Harp device" or "harp_device_type" in device_data:
        name = device_data["harp_device_type"]["name"]
        # remove spaces from name
        name = name.replace(" ", "")
        device_data["harp_device_type"]["name"] = name
        daq_device = HarpDevice(**device_data)
    elif "Neuropixels basestation" == device_type or "bsc_firmware_version" in device_data:
        daq_device = NeuropixelsBasestation(**device_data)
    elif device_type == "Open Ephys acquisition board" or "acquisition board" in device_data["name"].lower():
        daq_device = OpenEphysAcquisitionBoard(**device_data)
    else:
        try:
            daq_device = DAQDevice(**device_data)
        except Exception as e:
            print(f"Error creating DAQDevice: {e}")
            print(f"Device data: {device_data}")
            raise

    return daq_device.model_dump(), connections


def upgrade_monitor(data: dict) -> dict:
    """Upgrade Monitor device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Monitor")

    data = upgrade_positioned_device(data)

    monitor = Monitor(
        **data,
    )

    return monitor.model_dump()


def upgrade_olfactometer(data: dict) -> tuple[dict, list]:
    """Upgrade Olfactometer device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Olfactometer")
    connections = []

    # Pull computer_name and create a connection if present
    if "computer_name" in data and data["computer_name"]:
        if data["computer_name"]:
            connections.append(
                {
                    "receive": data["name"],
                    "send": data["computer_name"],
                }
            )
        remove(data, "computer_name")

    olfactometer = Olfactometer(
        **data,
    )

    return olfactometer.model_dump(), connections


def upgrade_lick_spout(data: dict) -> dict:
    """Upgrade LickSpout device data from v1.x to v2.0."""

    data = basic_device_checks(data, "LickSpout")

    if "solenoid_valve" in data and data["solenoid_valve"]:
        data["solenoid_valve"] = upgrade_generic_device_with_name(data.get("solenoid_valve", {}), "Solenoid valve")

    if "lick_sensor" in data and data["lick_sensor"]:
        data["lick_sensor"] = upgrade_generic_device_with_name(data.get("lick_sensor", {}), "Lick sensor")
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


def upgrade_stimulus_device(data: dict) -> tuple[dict, list]:
    """Upgrade stimulus device data from v1.x to v2.0."""

    # Figure out which stimulus device type this is and use the appropriate upgrader
    device_type = data.get("device_type")

    if device_type == "Monitor":
        return upgrade_monitor(data), []
    elif device_type == "Olfactometer":
        return upgrade_olfactometer(data)
    elif device_type == "Reward delivery":
        return upgrade_lick_spout_assembly(data), []
    elif device_type == "Speaker":
        return upgrade_speaker(data), []
    else:
        raise ValueError(f"Unsupported stimulus device type: {device_type}")


def _handle_camera_connections(data: dict) -> list:
    """Handle camera connection data"""
    connections = []
    if "computer_name" in data:
        if data["computer_name"]:
            connections.append(
                {
                    "send": data["name"],
                    "receive": data["computer_name"],
                }
            )
        remove(data, "computer_name")
    return connections


def _normalize_camera_values(data: dict) -> None:
    """Normalize camera-specific values"""
    if "cooling" in data and (not data["cooling"] or data["cooling"] == "None"):
        data["cooling"] = "No cooling"

    if "bin_mode" in data and data["bin_mode"] == "None":
        data["bin_mode"] = "No binning"

    if "frame_rate_unit" in data and data["frame_rate_unit"] == "Hertz":
        data["frame_rate_unit"] = "hertz"


def _handle_camera_dimensions(data: dict) -> None:
    """Handle camera pixel dimensions"""
    if "pixel_width" in data:
        data["sensor_width"] = data["pixel_width"]
        remove(data, "pixel_width")
    if "pixel_height" in data:
        data["sensor_height"] = data["pixel_height"]
        remove(data, "pixel_height")


def _handle_camera_software_and_format(data: dict) -> None:
    """Handle camera software and sensor format"""
    if "recording_software" in data and data["recording_software"]:
        data["recording_software"] = upgrade_software(data.get("recording_software", {}))

    if "sensor_format" in data and data["sensor_format"]:
        if "sensor_format_unit" not in data or not data["sensor_format_unit"]:
            data["sensor_format_unit"] = "unknown"


def upgrade_camera(data: dict) -> tuple[dict, list]:
    """Upgrade Camera device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Camera")

    # Handle connections
    connections = _handle_camera_connections(data)

    # Normalize camera values
    _normalize_camera_values(data)

    # Remove obsolete fields
    remove(data, "max_frame_rate")  # no idea when that was in v1.x
    remove(data, "format_unit")

    # Handle dimensions
    _handle_camera_dimensions(data)

    # Handle software and format
    _handle_camera_software_and_format(data)

    camera = Camera(**data)
    return camera.model_dump(), connections


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

    data = upgrade_generic_device_with_name(data, "Lens")

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


def upgrade_camera_assembly(data: dict) -> tuple[dict, list]:
    """Upgrade CameraAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    if "scope_assembly_name" in data and not data.get("name"):
        data["name"] = data["scope_assembly_name"]
        remove(data, "scope_assembly_name")
    if "camera_assembly_name" in data and not data.get("name"):
        data["name"] = data["camera_assembly_name"]
        remove(data, "camera_assembly_name")
    data = add_name(data, "CameraAssembly")

    connections = []

    if "filter" in data and data["filter"]:
        data["filter"] = upgrade_filter(data.get("filter", {}))
    camera_data, camera_connections = upgrade_camera(data.get("camera", {}))
    data["camera"] = camera_data
    connections.extend(camera_connections)
    data["lens"] = upgrade_lens(data.get("lens", {}))

    if "camera_target" not in data or not data["camera_target"]:
        if "probe" in data["camera"]["name"].lower():
            data["target"] = CameraTarget.BRAIN
            relative_positions = [AnatomicalRelative.SUPERIOR]
    else:
        data["target"], relative_positions = parse_camera_target(data.get("camera_target", ""))

    if "target" not in data:
        data["target"] = CameraTarget.OTHER
        relative_positions = []

    remove(data, "camera_target")
    remove(data, "notes")

    data = upgrade_positioned_device(data, relative_positions)

    camera_assembly = CameraAssembly(
        **data,
    )

    return camera_assembly.model_dump(), connections


def upgrade_manipulator(data: dict) -> dict:
    """Upgrade Manipulator device data from v1.x to v2.0."""

    data = basic_device_checks(data, "Manipulator")

    manipulator = Manipulator(**data)

    return manipulator.model_dump()


def upgrade_ephys_probe(data: dict) -> tuple[dict, list, list]:
    """Upgrade EphysProbe device data from v1.x to v2.0."""

    data = basic_device_checks(data, "EphysProbe")

    lasers = []
    connections = []
    if "lasers" in data and data["lasers"]:
        # Create the lasers separately
        lasers = [upgrade_light_source(laser) for laser in data["lasers"]]
        # Also store the connections
        connections = []
        for laser in lasers:
            connections.append(
                Connection(
                    source_device=laser["name"],
                    target_device=data["name"],
                ).model_dump()
            )

    remove(data, "lasers")

    # Handle headstage if present
    if "headstage" in data and data["headstage"]:
        if "headstage_model" in data["headstage"] and data["headstage"]["headstage_model"]:
            data["headstage"]["notes"] = (
                data["headstage"].get("notes", "")
                + f" (v1v2 upgrade): headstage model was '{data["headstage"]['headstage_model']}'."
            ).strip()
        remove(data["headstage"], "headstage_model")
        data["headstage"] = upgrade_generic_device_with_name(data["headstage"], "Headstage")

    ephys_probe = EphysProbe(**data)

    return ephys_probe.model_dump(), lasers, connections


def upgrade_ephys_assembly(data: dict) -> tuple[dict, list, list]:
    """Upgrade EphysAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    if "ephys_assembly_name" in data:
        data["name"] = data["ephys_assembly_name"]
        remove(data, "ephys_assembly_name")
    data = add_name(data, "EphysAssembly")

    # Upgrade the manipulator
    if "manipulator" in data:
        data["manipulator"] = upgrade_manipulator(data["manipulator"])

    opto_lasers = []
    opto_connections = []

    # Upgrade the probes array
    if "probes" in data:
        upgraded_probes = []
        for probe in data["probes"]:
            upgraded_probe, lasers, connections = upgrade_ephys_probe(probe)
            upgraded_probes.append(upgraded_probe)
            opto_lasers.extend(lasers)
            opto_connections.extend(connections)
        data["probes"] = upgraded_probes

    # Create EphysAssembly object
    ephys_assembly = EphysAssembly(**data)

    return ephys_assembly.model_dump(), opto_lasers, opto_connections


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

    if "total_length" in data and not data["total_length"]:
        data["total_length"] = 0
        data["notes"] = "(v1v2 upgrade): total_length was not specified, set to 0."

    fiber_probe = FiberProbe(**data)

    return fiber_probe.model_dump()


def upgrade_detector(data: dict) -> tuple[dict, list]:
    """Upgrade detector data to the new model."""

    data = basic_device_checks(data, "Detector")
    connections = []

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
            connections.append(
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

    return detector.model_dump(), connections


def upgrade_fiber_patch_cord(data: dict) -> dict:
    """Upgrade FiberPatchCord device data from v1.x to v2.0."""

    data = basic_device_checks(data, "FiberPatchCord")

    fiber_patch_cord = FiberPatchCord(**data)

    return fiber_patch_cord.model_dump()


def upgrade_laser_assembly(data: dict) -> dict:
    """Upgrade LaserAssembly device data from v1.x to v2.0."""

    # Perform basic device checks
    if "laser_assembly_name" in data:
        data["name"] = data["laser_assembly_name"]
        remove(data, "laser_assembly_name")

    # Add a generic name if not present
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
        data["collimator"] = upgrade_generic_device_with_name(data["collimator"], "Collimator")
    else:
        # Collimator missing, create a generic one
        data["collimator"] = Device(
            name="unknown collimator",
        )

    # Upgrade the fiber (mapped from "fiber" to "fiber" but using FiberPatchCord type)
    if "fiber" in data and data["fiber"]:
        data["fiber"] = upgrade_fiber_patch_cord(data["fiber"])
    else:
        # Fiber missing, create a generic one
        data["fiber"] = FiberPatchCord(
            name="unknown fiber",
            core_diameter=0,
            numerical_aperture=0,
        )

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
