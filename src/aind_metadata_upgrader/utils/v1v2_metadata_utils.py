"""Metadata level utilities"""

from datetime import datetime, timedelta
from aind_data_schema.core.procedures import Procedures
from aind_data_schema.core.instrument import Instrument
from aind_data_schema.components.devices import Device
from pydantic import ValidationError

from aind_metadata_upgrader.utils.v1v2_inst_id_repair import (
    repair_instrument_id_mismatch,  # noqa: F401 – re-exported for callers
)


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


def repair_acquisition_timezone(data: dict) -> dict:
    """If acquisition_start_time has a non-UTC timezone, try reinterpreting all UTC-labeled
    acquisition_end_time and data stream / stimulus epoch times as that same timezone.

    The fix is only applied if, after the reinterpretation, every stream and epoch time
    is properly contained within the acquisition_start_time / acquisition_end_time window.
    This guards against incorrectly patching records where UTC is genuinely correct.

    Handles both string and datetime values (strings from raw v1 JSON; datetime objects
    from model_dump() output of upgraded records).
    """
    if "acquisition" not in data:
        return data

    acquisition = data["acquisition"]
    start_time_raw = acquisition.get("acquisition_start_time")

    if not start_time_raw:
        return data

    def _to_dt(v):
        """Normalise a raw string or datetime to an aware datetime, or return None."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return None

    start_time = _to_dt(start_time_raw)
    if start_time is None:
        return data

    # Only proceed if start_time has a non-UTC timezone
    if start_time.tzinfo is None or start_time.utcoffset() == timedelta(0):
        return data

    start_tz = start_time.tzinfo

    def _fix_if_utc(v):
        """Reinterpret a UTC value as start_tz; leave non-UTC values as-is.
        Returns a datetime object."""
        dt = _to_dt(v)
        if dt is None:
            return v
        if dt.tzinfo is not None and dt.utcoffset() == timedelta(0):
            return dt.replace(tzinfo=start_tz)
        return dt

    # Build candidate end time
    end_time_raw = acquisition.get("acquisition_end_time")
    candidate_end = _fix_if_utc(end_time_raw) if end_time_raw is not None else None

    # Build candidate stream times
    candidate_streams = []
    for stream in acquisition.get("data_streams", []):
        ss = _fix_if_utc(stream.get("stream_start_time")) if stream.get("stream_start_time") is not None else None
        se = _fix_if_utc(stream.get("stream_end_time")) if stream.get("stream_end_time") is not None else None
        candidate_streams.append((ss, se))

    # Build candidate stimulus epoch times
    candidate_epochs = []
    for epoch in acquisition.get("stimulus_epochs", []):
        es = _fix_if_utc(epoch.get("stimulus_start_time")) if epoch.get("stimulus_start_time") is not None else None
        ee = _fix_if_utc(epoch.get("stimulus_end_time")) if epoch.get("stimulus_end_time") is not None else None
        candidate_epochs.append((es, ee))

    # Validate: all streams and epochs must be within [start_time, candidate_end]
    acq_start = start_time
    acq_end = _to_dt(candidate_end) if not isinstance(candidate_end, datetime) else candidate_end

    def _within(t):
        if t is None or not isinstance(t, datetime):
            return True
        if acq_start and t.tzinfo and t < acq_start:
            return False
        if acq_end and t.tzinfo and t > acq_end:
            return False
        return True

    all_valid = all(_within(t) for pair in candidate_streams + candidate_epochs for t in pair)

    if not all_valid:
        return data

    # Apply the fix
    if end_time_raw is not None:
        data["acquisition"]["acquisition_end_time"] = candidate_end

    for stream, (ss, se) in zip(acquisition.get("data_streams", []), candidate_streams):
        if stream.get("stream_start_time") is not None:
            stream["stream_start_time"] = ss
        if stream.get("stream_end_time") is not None:
            stream["stream_end_time"] = se

    for epoch, (es, ee) in zip(acquisition.get("stimulus_epochs", []), candidate_epochs):
        if epoch.get("stimulus_start_time") is not None:
            epoch["stimulus_start_time"] = es
        if epoch.get("stimulus_end_time") is not None:
            epoch["stimulus_end_time"] = ee

    return data


def repair_naive_acquisition_times(data: dict) -> dict:
    """Assign Pacific timezone to any acquisition timestamps that are still naive (no timezone info).

    This is the final fallback after repair_acquisition_timezone has run: if any times still
    lack a timezone, attach America/Los_Angeles as the safest default for AIND data.
    """
    from zoneinfo import ZoneInfo

    pacific = ZoneInfo("America/Los_Angeles")

    if "acquisition" not in data:
        return data

    acquisition = data["acquisition"]

    def _ensure(v):
        if v is None:
            return v
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=pacific)
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=pacific)
            return dt
        return v

    for field in ("acquisition_start_time", "acquisition_end_time"):
        if acquisition.get(field) is not None:
            acquisition[field] = _ensure(acquisition[field])

    for stream in acquisition.get("data_streams", []):
        for field in ("stream_start_time", "stream_end_time"):
            if stream.get(field) is not None:
                stream[field] = _ensure(stream[field])

    for epoch in acquisition.get("stimulus_epochs", []):
        for field in ("stimulus_start_time", "stimulus_end_time"):
            if epoch.get(field) is not None:
                epoch[field] = _ensure(epoch[field])

    return data


def repair_metadata(data: dict) -> dict:
    """Repair the full metadata record, checking for common issues"""

    data = repair_instrument_id_mismatch(data)
    data = repair_missing_active_devices(data)
    data = repair_connection_devices(data)
    data = repair_creation_time(data)
    data = repair_acquisition_timezone(data)
    data = repair_naive_acquisition_times(data)

    return data
