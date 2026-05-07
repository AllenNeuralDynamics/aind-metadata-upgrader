"""Metadata level utilities"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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


def _parse_dt(v):
    """Normalise a string or datetime to a datetime object, or return None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return None


def _reinterpret_utc_as(v, tz):
    """If v parses to a UTC-aware datetime, replace its tzinfo with tz (reinterpret, not convert).
    Otherwise return the parsed datetime unchanged."""
    dt = _parse_dt(v)
    if dt is None:
        return v
    if dt.tzinfo is not None and dt.utcoffset() == timedelta(0):
        return dt.replace(tzinfo=tz)
    return dt


def _within_bounds(t, acq_start, acq_end):
    """Return True if t (datetime or None) lies within [acq_start, acq_end]."""
    if t is None or not isinstance(t, datetime):
        return True
    if acq_start and t.tzinfo and t < acq_start:
        return False
    if acq_end and t.tzinfo and t > acq_end:
        return False
    return True


def _ensure_tz(v, tz):
    """Parse v to a datetime and attach tz if it is naive; aware datetimes pass through."""
    if v is None:
        return v
    dt = _parse_dt(v)
    if dt is None:
        return v
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def _reinterpret_pair(obj, fields, tz):
    """Return a tuple of reinterpreted values for the two fields in obj."""
    return tuple(_reinterpret_utc_as(obj.get(f), tz) for f in fields)


def _apply_pair(obj, fields, values):
    """Write back non-None candidate values into obj for the given fields."""
    for field, value in zip(fields, values):
        if obj.get(field) is not None:
            obj[field] = value


def _non_utc_tz(start_raw):
    """Return the tzinfo from start_raw if it is a non-UTC aware datetime, else None."""
    start_time = _parse_dt(start_raw)
    if start_time is None:
        return None
    if start_time.tzinfo is None or start_time.utcoffset() == timedelta(0):
        return None
    return start_time.tzinfo, start_time


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
    result = _non_utc_tz(acquisition.get("acquisition_start_time"))
    if result is None:
        return data
    start_tz, start_time = result

    candidate_end = _reinterpret_utc_as(acquisition.get("acquisition_end_time"), start_tz)
    candidate_streams = [_reinterpret_pair(s, _STREAM_FIELDS, start_tz) for s in acquisition.get("data_streams", [])]
    candidate_epochs = [_reinterpret_pair(e, _EPOCH_FIELDS, start_tz) for e in acquisition.get("stimulus_epochs", [])]

    acq_end = _parse_dt(candidate_end)
    all_valid = all(
        _within_bounds(t, start_time, acq_end)
        for pair in candidate_streams + candidate_epochs
        for t in pair
    )
    if not all_valid:
        return data

    _apply_pair(acquisition, ("acquisition_end_time",), (candidate_end,))
    for stream, pair in zip(acquisition.get("data_streams", []), candidate_streams):
        _apply_pair(stream, _STREAM_FIELDS, pair)
    for epoch, pair in zip(acquisition.get("stimulus_epochs", []), candidate_epochs):
        _apply_pair(epoch, _EPOCH_FIELDS, pair)

    return data


_PACIFIC = ZoneInfo("America/Los_Angeles")
_ACQ_TOP_FIELDS = ("acquisition_start_time", "acquisition_end_time")
_STREAM_FIELDS = ("stream_start_time", "stream_end_time")
_EPOCH_FIELDS = ("stimulus_start_time", "stimulus_end_time")


def repair_naive_acquisition_times(data: dict) -> dict:
    """Assign Pacific timezone to any acquisition timestamps that are still naive (no timezone info).

    This is the final fallback after repair_acquisition_timezone has run: if any times still
    lack a timezone, attach America/Los_Angeles as the safest default for AIND data.
    """
    if "acquisition" not in data:
        return data

    acquisition = data["acquisition"]

    for field in _ACQ_TOP_FIELDS:
        if acquisition.get(field) is not None:
            acquisition[field] = _ensure_tz(acquisition[field], _PACIFIC)

    for stream in acquisition.get("data_streams", []):
        for field in _STREAM_FIELDS:
            if stream.get(field) is not None:
                stream[field] = _ensure_tz(stream[field], _PACIFIC)

    for epoch in acquisition.get("stimulus_epochs", []):
        for field in _EPOCH_FIELDS:
            if epoch.get(field) is not None:
                epoch[field] = _ensure_tz(epoch[field], _PACIFIC)

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
