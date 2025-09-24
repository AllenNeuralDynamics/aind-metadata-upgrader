"""Metadata level utilities"""

from datetime import datetime
from aind_data_schema.core.procedures import Procedures
from aind_data_schema.core.instrument import Instrument
from aind_data_schema.components.devices import Device


# List of acquisition IDs where the instrument_id needs to be copied from instrument to acquisition
SHORT_ACQ_ID_LIST = ["5B", "4D", "MESO.1", "MESO.2", "5A", "4A", "4B", "4C"]
# List of acquisition IDs where the instrument_id needs to be copied from acquisition to instrument
LONG_ACQ_ID_LIST = ["442_Bergamo_2p_photostim"]
# Instrument/Acquisition pairs where id copied from instrument -> acquisition
PAIRED_INSTRUMENT_ACQUISITION_IDS = [
    ("342_NP3_240417", "342_NP3_240401"),
]


def _handle_spim_modality_mismatch(data: dict) -> dict:
    """Handle instrument ID mismatch for SPIM modality"""
    if "acquisition" in data and data["acquisition"] and "instrument_id" in data["acquisition"]:
        acquisition_instrument_id = data["acquisition"]["instrument_id"]
        if "instrument" in data and data["instrument"]:
            if "instrument_id" in data["instrument"]:
                instrument_id = data["instrument"]["instrument_id"]

                if acquisition_instrument_id != instrument_id:
                    data["instrument"]["instrument_id"] = acquisition_instrument_id
            else:
                raise ValueError("instrument.instrument_id is missing while acquisition.instrument_id is present.")
    return data


def _handle_general_id_mismatch(data: dict) -> dict:
    """Handle instrument ID mismatch for general cases"""
    if "acquisition" in data and data["acquisition"] and "instrument_id" in data["acquisition"]:
        if data["instrument"]["instrument_id"] in data["acquisition"]["instrument_id"]:
            # If the instrument instrument_id is contained within the acquisition instrument_id, copy it
            data["instrument"]["instrument_id"] = data["acquisition"]["instrument_id"]
        elif data["acquisition"]["instrument_id"] in LONG_ACQ_ID_LIST:
            data["instrument"]["instrument_id"] = data["acquisition"]["instrument_id"]
        elif data["acquisition"]["instrument_id"] in SHORT_ACQ_ID_LIST:
            data["acquisition"]["instrument_id"] = data["instrument"]["instrument_id"]
        else:
            # Check the paired list
            acquisition_id = data["acquisition"]["instrument_id"]
            instrument_id = data["instrument"]["instrument_id"]
            if (instrument_id, acquisition_id) in PAIRED_INSTRUMENT_ACQUISITION_IDS:
                data["acquisition"]["instrument_id"] = instrument_id
    return data


def repair_instrument_id_mismatch(data: dict) -> dict:
    """Repair mismatched instrument IDs between acquisition and instrument sections"""

    if "instrument" not in data or "acquisition" not in data:
        return data

    modalities = data.get("data_description", {}).get("modalities", [])
    if any(modality["abbreviation"] == "SPIM" for modality in modalities):
        return _handle_spim_modality_mismatch(data)
    else:
        return _handle_general_id_mismatch(data)


def get_active_devices(data: dict) -> list:
    """Get a list of active devices from the acquisition data streams and stimulus epochs."""

    active_devices = []

    if "acquisition" in data:
        # Collect active devices from data streams
        if "data_streams" in data["acquisition"]:
            for data_stream in data["acquisition"]["data_streams"]:
                active_devices.extend(data_stream.get("active_devices", []))

        # Collective active devices from stimulus epochs
        if "stimulus_epochs" in data["acquisition"]:
            for stimulus_epoch in data["acquisition"]["stimulus_epochs"]:
                active_devices.extend(stimulus_epoch.get("active_devices", []))

    return active_devices


def repair_missing_active_devices(data: dict) -> dict:
    """Create missing devices that are referenced in active_devices but not in instrument components"""

    if "acquisition" not in data or "instrument" not in data:
        return data

    # Collect active devices from data streams
    active_devices = get_active_devices(data)

    # Collect existing device names
    device_names = []
    if data.get("instrument"):
        instrument = Instrument.model_validate(data.get("instrument"))
        device_names.extend(instrument.get_component_names())
    if data.get("procedures"):
        procedures = Procedures.model_validate(data["procedures"])
        device_names.extend(procedures.get_device_names())

    # Check if all active devices are in the available devices
    if not all(device in device_names for device in active_devices):
        missing_devices = set(active_devices) - set(device_names)
        # Create missing devices with default names
        for device in missing_devices:
            new_device = Device(
                name=device,
                notes=(
                    "(v1v2 upgrade metadata) This device was not found in the components list, "
                    "but is referenced in Acquisition.active_devices."
                ),
            )
            data["instrument"]["components"].append(new_device.model_dump())

    return data


def get_connection_device_names(data: dict) -> list:
    """Get a list of device names referenced in connections from the instrument and acquisition data."""

    connection_device_names = []

    # Check instrument connections
    if data.get("instrument") and "connections" in data["instrument"]:
        for connection in data["instrument"]["connections"]:
            connection_device_names.append(connection["source_device"])
            connection_device_names.append(connection["target_device"])

    # Check acquisition data stream connections
    if data.get("acquisition") and "data_streams" in data["acquisition"]:
        for data_stream in data["acquisition"]["data_streams"]:
            if "connections" in data_stream:
                for connection in data_stream["connections"]:
                    connection_device_names.append(connection["source_device"])
                    connection_device_names.append(connection["target_device"])

    return connection_device_names


def repair_connection_devices(data: dict) -> dict:
    """Create missing devices that are referenced in connections but not in instrument components"""

    if "instrument" not in data:
        return data

    # Collect all device names referenced in connections
    connection_devices = get_connection_device_names(data)

    # Collect existing device names
    device_names = []
    if data.get("instrument"):
        instrument = Instrument.model_validate(data.get("instrument"))
        device_names.extend(instrument.get_component_names())
    if data.get("procedures"):
        procedures = Procedures.model_validate(data["procedures"])
        device_names.extend(procedures.get_device_names())

    # Check if all connection devices are in the available devices
    for device_name in connection_devices:
        if device_name not in device_names:
            # Create a new device with a note indicating it was missing
            new_device = Device(
                name=device_name,
                notes=(
                    "(v1v2 upgrade metadata) This device was not found in the components list, "
                    "but is referenced in connections."
                ),
            )
            data["instrument"]["components"].append(new_device.model_dump())

    return data


def repair_creation_time(data: dict) -> dict:
    """If the data_description.creation_time is before the acquisition.acquisition_end_time, copy the end time"""

    if "data_description" not in data or "acquisition" not in data:
        return data

    creation_time = data["data_description"].get("creation_time")
    acquisition_end_time = data["acquisition"].get("acquisition_end_time")

    # Convert to datetime objects if they are strings
    if isinstance(creation_time, str):
        creation_time = datetime.fromisoformat(creation_time.replace("Z", "+00:00"))
    if isinstance(acquisition_end_time, str):
        acquisition_end_time = datetime.fromisoformat(acquisition_end_time.replace("Z", "+00:00"))

    if creation_time and acquisition_end_time:
        # If creation time is before acquisition end time, copy the end time
        if creation_time < acquisition_end_time:
            data["data_description"]["creation_time"] = acquisition_end_time

    return data


def repair_metadata(data: dict) -> dict:
    """Repair the full metadata record, checking for common issues"""

    data = repair_instrument_id_mismatch(data)
    data = repair_missing_active_devices(data)
    data = repair_connection_devices(data)
    data = repair_creation_time(data)

    return data
