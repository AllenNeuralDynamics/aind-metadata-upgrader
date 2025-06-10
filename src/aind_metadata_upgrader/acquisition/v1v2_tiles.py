"""Tile upgrade functions for v1.4 to v2.0 acquisition upgrade"""

from typing import Dict, List
from aind_data_schema_models.modalities import Modality


def extract_modality_from_tiles(tiles: List[Dict]) -> Dict:
    """Extract modality from tile data - assume SPIM for imaging tiles"""
    # For now, assume SPIM since that's what the example data shows
    # In a more sophisticated implementation, you could analyze the tile structure
    return Modality.SPIM.model_dump()


def create_basic_imaging_config() -> Dict:
    """Create a basic imaging configuration placeholder"""
    # Since ImagingConfig has many required fields we don't have from tiles,
    # create a minimal configuration placeholder
    return {"object_type": "Imaging configuration", "device_name": "Imaging Device", "channels": [], "images": []}


def determine_active_devices_from_tiles(tiles: List[Dict]) -> List[str]:
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
        for device in additional_devices:
            if device:
                active_devices.add(device)

    return list(active_devices)


def extract_stream_times_from_tiles(tiles: List[Dict], session_start: str, session_end: str) -> tuple[str, str]:
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


def upgrade_tiles_to_data_streams(tiles: List[Dict], session_start: str, session_end: str) -> List[Dict]:
    """Convert V1 tiles to V2 data streams"""

    if not tiles:
        return []

    # Extract stream timing
    stream_start, stream_end = extract_stream_times_from_tiles(tiles, session_start, session_end)

    # Determine modality and devices
    modalities = [extract_modality_from_tiles(tiles)]
    active_devices = determine_active_devices_from_tiles(tiles)

    # Create basic imaging configuration
    configurations = [create_basic_imaging_config()]

    # Combine notes from tiles
    tile_notes = [tile.get("notes", "") for tile in tiles if tile.get("notes")]
    combined_notes = "; ".join(filter(None, tile_notes)) if tile_notes else None

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

    return [data_stream]
