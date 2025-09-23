"""Tile upgrade functions for v1.4 to v2.0 acquisition upgrade"""

from typing import Optional

from aind_data_schema.components.configs import (
    Channel,
    DetectorConfig,
    Immersion,
    LaserConfig,
    SampleChamberConfig,
    TriggerType,
    DeviceConfig,
)
from aind_data_schema.core.acquisition import DataStream
from aind_data_schema_models.devices import ImmersionMedium
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.units import PowerUnit, SizeUnit, TimeUnit


FILTER_MAPPING = {
    "FF01-469/35-25": 469,
    "FF01-525/50-25": 525,
    "FF01-593/40-25": 593,
    "FF01-640/30-25": 640,
    "FF01-700/75-25": 700,
    "FF01-750/50-25": 750,
}


def _create_detector_config() -> DetectorConfig:
    """Create default detector config for tiles"""
    return DetectorConfig(
        device_name="unknown_detector",  # Will need to be filled in later
        exposure_time=1.0,  # Default value
        exposure_time_unit=TimeUnit.MS,
        trigger_type=TriggerType.INTERNAL,  # Default value
    )


def _create_laser_config_from_channel(channel_data: dict) -> list:
    """Create laser configurations from channel data"""
    light_source_configs = []

    if "laser_wavelength" in channel_data:
        laser_config_params = {
            "device_name": f"laser_{channel_data['laser_wavelength']}nm",
            "wavelength": channel_data["laser_wavelength"],
            "wavelength_unit": SizeUnit.NM,
        }

        # Add power if available
        if "laser_power" in channel_data:
            laser_config_params["power"] = channel_data["laser_power"]
            power_unit = channel_data.get("laser_power_unit", "milliwatt")
            laser_config_params["power_unit"] = PowerUnit.MW if power_unit == "milliwatt" else PowerUnit.MW

        laser_config = LaserConfig(**laser_config_params)
        light_source_configs.append(laser_config)

    return light_source_configs


def _create_laser_config_from_light_sources(channel_data: dict, light_sources: list[dict]) -> list:
    """Create laser configurations from existing light sources"""
    light_source_configs = []

    if "excitation_wavelength" in channel_data:
        excitation_wavelength = int(channel_data["excitation_wavelength"])

        for i, light_source in enumerate(light_sources):
            if light_source.get("wavelength") == excitation_wavelength:
                name = light_source.get("name", f"Laser {i}") or f"Laser {i}"
                light_source_configs.append(
                    LaserConfig(
                        device_name=name,
                        wavelength=excitation_wavelength,
                    )
                )

    return light_source_configs


def _create_emission_filters(channel_data: dict, fluorescence_filters: list[dict]) -> tuple[list, Optional[int]]:
    """Create emission filters and wavelength from fluorescence filters"""
    filter_wheel_index = channel_data.get("filter_wheel_index")
    emission_filters = []
    emission_wavelength = None

    for i, filter_config in enumerate(fluorescence_filters):
        if filter_config.get("filter_wheel_index") == filter_wheel_index:
            if filter_config.get("model") in FILTER_MAPPING:
                name = filter_config.get("name", f"Filter {i}") or f"Filter {i}"
                emission_filters.append(DeviceConfig(device_name=name))

                if filter_config.get("model") in FILTER_MAPPING:
                    emission_wavelength = FILTER_MAPPING[filter_config["model"]]
                else:
                    print(f"Unknown filter model: {filter_config.get('model')}")

    return emission_filters, emission_wavelength


def extract_channels_from_tiles(
    tiles: list[dict], fluorescence_filters: list[dict], light_sources: list[dict]
) -> list[Channel]:
    """Extract and accumulate unique channels from tile data"""
    channels_dict = {}  # Use dict to avoid duplicates by channel name

    for tile in tiles:
        channel_data = tile.get("channel", {})
        if not channel_data:
            continue

        channel_name = channel_data.get("channel_name")
        if not channel_name or channel_name in channels_dict:
            continue

        # Create detector config
        detector_config = _create_detector_config()

        # Create laser configs
        light_source_configs = _create_laser_config_from_channel(channel_data)
        if not light_source_configs:
            light_source_configs = _create_laser_config_from_light_sources(channel_data, light_sources)

        # Create emission filters
        emission_filters, emission_wavelength = _create_emission_filters(channel_data, fluorescence_filters)

        # Create the channel
        channel = Channel(
            channel_name=channel_name,
            detector=detector_config,
            light_sources=light_source_configs,
            variable_power=False,
            emission_filters=emission_filters,
            emission_wavelength=emission_wavelength,
            emission_wavelength_unit=SizeUnit.NM,
        )

        channels_dict[channel_name] = channel

    return list(channels_dict.values())


def extract_modality_from_tiles(tiles: list[dict]) -> dict:
    """Extract modality from tile data - assume SPIM for imaging tiles"""
    # For now, assume SPIM since that's what the example data shows
    # In a more sophisticated implementation, you could analyze the tile structure
    return Modality.SPIM.model_dump()


def create_basic_imaging_config(channels: list[Channel]) -> dict:
    """Create a basic imaging configuration placeholder"""
    # Since ImagingConfig has many required fields we don't have from tiles,
    # create a minimal configuration placeholder
    return {
        "object_type": "Imaging config",
        "device_name": "unknown",
        "channels": [channel.model_dump() for channel in channels],
        "images": [],
    }


def determine_active_devices_from_tiles(tiles: list[dict]) -> list[str]:
    """Extract active device names from tile data"""
    active_devices = set()

    for tile in tiles:
        channel = tile.get("channel", {})

        # Extract device names from channel info
        if "light_source_name" in channel and channel["light_source_name"]:
            active_devices.add(channel["light_source_name"])

        if "detector_name" in channel and channel["detector_name"]:
            active_devices.add(channel["detector_name"])

        # Add filter names
        filter_names = channel.get("filter_names", [])
        for filter_name in filter_names:
            if filter_name:
                active_devices.add(filter_name)

        # Add any additional device names
        additional_devices = channel.get("additional_device_names", [])
        if additional_devices:
            for device in additional_devices:
                if device:
                    active_devices.add(device)

    return list(active_devices)


def extract_stream_times_from_tiles(tiles: list[dict], session_start: str, session_end: str) -> tuple[str, str]:
    """Extract stream start/end times from tiles, falling back to session times"""

    # Look for acquisition times in tiles
    tile_start_times = []
    tile_end_times = []

    for tile in tiles:
        if tile.get("acquisition_start_time"):
            tile_start_times.append(tile["acquisition_start_time"])
        if tile.get("acquisition_end_time"):
            tile_end_times.append(tile["acquisition_end_time"])

    # Use tile times if available, otherwise fall back to session times
    if tile_start_times:
        stream_start = min(tile_start_times)
    else:
        stream_start = session_start

    if tile_end_times:
        stream_end = max(tile_end_times)
    else:
        stream_end = session_end

    return stream_start, stream_end


MEDIUM_MAP = {
    "Cargille 1.52": ImmersionMedium.OIL,
    "Cargille 1.5200": ImmersionMedium.OIL,
    "Cargille Oil 1.5200": ImmersionMedium.OIL,
    "Cargille oil 1.5200": ImmersionMedium.OIL,
    "EasyIndex": ImmersionMedium.EASYINDEX,
    "0.05x SSC": ImmersionMedium.WATER,
    "ACB": ImmersionMedium.ACB,
    "Ethyl cinnamate": ImmersionMedium.ECI,
}


def upgrade_immersion(data: dict) -> dict:
    """Upgrade an immersion dictionary to the new Immersion schema"""

    if "medium" in data:
        # First check for old string mappings
        if any(key in data["medium"] for key in MEDIUM_MAP.keys()):
            # Find the matching medium key and update it
            for old_key, new_medium in MEDIUM_MAP.items():
                if old_key in data["medium"]:
                    data["medium"] = new_medium
                    break
        else:
            # Check if it's a correct enum value but with wrong capitalization
            medium_lower = data["medium"].lower()
            # Try to match against all enum values (case-insensitive)
            for enum_member in ImmersionMedium:
                if medium_lower in enum_member.value.lower():
                    data["medium"] = enum_member.value
                    break

    return Immersion(**data).model_dump()


def upgrade_tiles_to_data_stream(
    tiles: list[dict],
    session_start: str,
    session_end: str,
    chamber_immersion: dict,
    sample_immersion: Optional[dict],
    device_name: str,
    software: list,
    fluorescence_filters: list[dict],
    light_sources: list[dict],
) -> list[dict]:
    """Convert V1 tiles to V2 data streams"""

    if not tiles:
        return []

    # Add code to build up list of channels from tiles
    channels = extract_channels_from_tiles(tiles, fluorescence_filters, light_sources)

    # Extract stream timing
    stream_start, stream_end = extract_stream_times_from_tiles(tiles, session_start, session_end)

    # Determine modality and devices
    modalities = [extract_modality_from_tiles(tiles)]
    active_devices = determine_active_devices_from_tiles(tiles)

    chamber_config = SampleChamberConfig(
        device_name=device_name,
        chamber_immersion=upgrade_immersion(chamber_immersion),
        sample_immersion=upgrade_immersion(sample_immersion) if sample_immersion else None,
    ).model_dump()

    # Create basic imaging configuration
    configurations = [
        create_basic_imaging_config(channels),
        chamber_config,
    ]

    # Combine notes from tiles
    tile_notes = [tile.get("notes", "") for tile in tiles if tile.get("notes")]
    tile_notes = set(tile_notes)  # Remove duplicates
    combined_notes = "; ".join(filter(None, tile_notes)) if tile_notes else None

    # Handle software
    if software:
        print(software)
        raise NotImplementedError("Software handling is not implemented yet.")

    # Create single data stream from all tiles
    data_stream = {
        "stream_start_time": stream_start,
        "stream_end_time": stream_end,
        "modalities": modalities,
        "code": None,
        "notes": combined_notes,
        "active_devices": active_devices,
        "configurations": configurations,
        "connections": [],
    }

    return [DataStream(**data_stream).model_dump()]
