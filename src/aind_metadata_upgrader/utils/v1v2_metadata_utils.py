"""Metadata level utilities"""

import re
from datetime import datetime
from aind_data_schema.core.procedures import Procedures
from aind_data_schema.core.instrument import Instrument
from aind_data_schema.components.devices import Device
from pydantic import ValidationError

from aind_metadata_upgrader.utils.v1v2_inst_id_repair import (
    repair_instrument_id_mismatch,  # noqa: F401 – re-exported for callers
)
from aind_metadata_upgrader.utils.v1v2_inst_id_repair import (
    BAD_INSTRUMENT_IDS as ECEPHYS_BAD_INSTRUMENT_IDS,
    LONG_ACQ_ID_LIST,
    PAIRED_INSTRUMENT_ACQUISITION_IDS,
    SHORT_ACQ_ID_LIST,
    _DATE_PATTERNS as _ECEPHYS_DATE_PATTERNS,
    _parse_rig_id_parts,
)


# ---------------------------------------------------------------------------
# Kept for backward compatibility – internal per-modality helpers
# ---------------------------------------------------------------------------


def _parse_rig_id_parts(rig_id: str):
    """Extract (prefix, date) from a rig ID string.

    Returns (rig_id, None) if no recognisable date is found.
    """
    for pattern, fmt in _ECEPHYS_DATE_PATTERNS:
        m = pattern.search(rig_id)
        if m:
            try:
                date = datetime.strptime(m.group(1), fmt)
                prefix = rig_id[: m.start()]
                return prefix, date
            except ValueError:
                continue
    return rig_id, None


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


def _handle_ecephys_id_mismatch(data: dict) -> dict:
    """Handle instrument ID mismatch for ecephys modality.

    Rules applied in order:
    1. Known-bad instrument IDs: overwrite instrument with acquisition value.
    2. Same content, only date formatting differs (YYYYMMDD vs YYYY-MM-DD):
       normalise by copying acquisition ID into instrument.
    3. Same base rig (prefix matches after punctuation normalisation):
       - If rig date is more recent, copy rig ID into acquisition.
       - If session date is more recent, raise ValueError.
       - If dates are equal (punctuation differs only), prefer rig.
    4. Different base prefix: prefer rig, copy rig ID into acquisition.
    """
    instrument_id = data["instrument"]["instrument_id"]
    acquisition_id = data["acquisition"]["instrument_id"]

    if not instrument_id or not acquisition_id:
        return data
    if instrument_id == acquisition_id:
        return data

    # Rule 1: explicitly bad instrument IDs
    if instrument_id in ECEPHYS_BAD_INSTRUMENT_IDS:
        data["instrument"]["instrument_id"] = acquisition_id
        return data

    # Rule 2: same content, only date separators differ
    if instrument_id.replace("-", "") == acquisition_id.replace("-", ""):
        # Use the acquisition (session) value which carries YYYY-MM-DD format
        data["instrument"]["instrument_id"] = acquisition_id
        return data

    # Rule 3/4: parse prefix and date from both sides
    rig_prefix, rig_date = _parse_rig_id_parts(instrument_id)
    session_prefix, session_date = _parse_rig_id_parts(acquisition_id)

    # Normalise prefixes: remove dots so NP.3 == NP3
    rig_prefix_norm = rig_prefix.replace(".", "") if rig_prefix else ""
    session_prefix_norm = session_prefix.replace(".", "") if session_prefix else ""

    if rig_prefix_norm == session_prefix_norm:
        # Same base rig — resolve by date
        if rig_date and session_date:
            if rig_date > session_date:
                data["acquisition"]["instrument_id"] = instrument_id
            elif rig_date < session_date:
                raise ValueError(
                    f"Session rig ID '{acquisition_id}' has a more recent date than "
                    f"instrument rig ID '{instrument_id}'. Cannot auto-resolve."
                )
            else:
                # Equal dates, prefix differed only in punctuation — prefer rig
                data["acquisition"]["instrument_id"] = instrument_id
        else:
            # Cannot parse dates; prefer rig
            data["acquisition"]["instrument_id"] = instrument_id
    else:
        # Different base prefix (e.g. 342_ vs unknown_) — prefer rig
        data["acquisition"]["instrument_id"] = instrument_id

    return data


def _handle_general_id_mismatch(data: dict) -> dict:
    """Handle instrument ID mismatch for general cases"""
    if "acquisition" not in data or not data["acquisition"]:
        return data
    if "instrument" not in data or not data["instrument"]:
        return data

    acquisition_id = data["acquisition"].get("instrument_id")
    instrument_id = data["instrument"].get("instrument_id")

    if not acquisition_id or not instrument_id:
        return data

    if acquisition_id == instrument_id:
        return data

    if instrument_id in acquisition_id:
        # If the instrument instrument_id is contained within the acquisition instrument_id, copy it
        data["instrument"]["instrument_id"] = acquisition_id
    elif acquisition_id in LONG_ACQ_ID_LIST:
        data["instrument"]["instrument_id"] = acquisition_id
    elif acquisition_id in SHORT_ACQ_ID_LIST:
        data["acquisition"]["instrument_id"] = instrument_id
    else:
        # Check the paired list
        if (instrument_id, acquisition_id) in PAIRED_INSTRUMENT_ACQUISITION_IDS:
            data["acquisition"]["instrument_id"] = instrument_id

    return data


# repair_instrument_id_mismatch is imported from v1v2_inst_id_repair and
# re-exported at the top of this module.


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
        try:
            procedures = Procedures.model_validate(data["procedures"])
            device_names.extend(procedures.get_device_names())
        except Exception as e:
            print(f"Failed to validate procedures to capture procedure device names: {e}")

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
        try:
            procedures = Procedures.model_validate(data["procedures"])
        except ValidationError:
            # Allow procedures to fail validation - use model_construct instead
            procedures = Procedures.model_construct(**data["procedures"])
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
