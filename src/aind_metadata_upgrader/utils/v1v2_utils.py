"""Shared utility functions for the AIND Metadata Upgrader."""

from aind_data_schema.components.identifiers import Software

from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization

MODALITY_MAP = {
    "SmartSPIM": Modality.SPIM,
}

counts = {}


def upgrade_v1_modalities(data: dict) -> list:
    """Upgrade v1.x modalities lists to the v2.0 format"""

    modalities = data.get("modality", [])

    if not isinstance(modalities, list):
        if isinstance(modalities, str):
            # Coerce single modality to it's object
            if modalities in MODALITY_MAP:
                modalities = [MODALITY_MAP[modalities].model_dump()]
            else:
                # Convert try to get a Modality object from abbreviation
                try:
                    modalities = [Modality.from_abbreviation(modalities).model_dump()]
                except Exception as e:
                    raise ValueError(f"Unsupported modality abbreviation: {modalities}") from e
        else:
            modalities = [modalities]

    return modalities


def add_name(data: dict, type: str) -> dict:
    """Add a name field if it's missing, keep track of counts in a global
    variable."""

    if "name" not in data or not data["name"]:
        global counts
        if type not in counts:
            counts[type] = 0
        counts[type] += 1
        name = f"{type} {counts[type]}"
        data["name"] = name

    return data


def repair_manufacturer(data: dict) -> dict:
    """Repair the manufacturer field to ensure it's an Organization object."""

    if "manufacturer" in data and isinstance(data["manufacturer"], str):
        # Convert string to Organization object
        data["manufacturer"] = Organization.from_name(data["manufacturer"]).model_dump()

    if "manufacturer" in data and isinstance(data["manufacturer"], dict):
        if data["manufacturer"]["name"] == "Other" and not data["notes"]:
            data["notes"] = (
                data["notes"] if data["notes"] else "" +
                " (v1v2 upgrade): 'manufacturer' was set to 'Other'" " and notes were empty, manufacturer is unknown."
            )

    if "manufacturer" not in data or not data["manufacturer"]:
        data["manufacturer"] = Organization.OTHER.model_dump()
        data["notes"] = (
                data["notes"] if data["notes"] else "" +
                " (v1v2 upgrade): 'manufacturer' field was missing, defaulting to 'Other'."
        )

    return data


def upgrade_device(data: dict) -> dict:
    """Remove old Device fields"""

    if "device_type" in data:
        del data["device_type"]
    if "path_to_cad" in data:
        del data["path_to_cad"]
    if "port_index" in data:
        del data["port_index"]
    if "daq_channel" in data:
        if data["daq_channel"]:
            raise ValueError("DAQ Channel has a value -- cannot upgrade record.")
        del data["daq_channel"]

    return data


def basic_device_checks(data: dict, type: str) -> dict:
    """Perform basic checks:

    - Check that name is set correctly or set to a default
    - Check that organization is not a string, but an Organization object
    """
    data = upgrade_device(data)
    data = add_name(data, type)
    data = repair_manufacturer(data)

    return data


def capitalize(data: dict, field: str) -> dict:
    """Capitalize the first letter of a field in the data dictionary."""

    if field in data and isinstance(data[field], str):
        data[field] = data[field].capitalize()

    return data


def remove(data: dict, field: str):
    """Remove a field from the data dictionary if it exists."""

    if field in data:
        del data[field]


def upgrade_software(data: dict) -> dict:
    """Upgrade software class from v1.x to v2.0"""

    remove(data, "url")
    remove(data, "parameters")

    return data
