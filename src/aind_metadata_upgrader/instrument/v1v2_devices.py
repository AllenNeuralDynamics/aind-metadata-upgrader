"""Upgraders for specific devices from v1 to v2."""

from aind_data_schema.components.devices import (
    Enclosure,
    Objective,
)

from aind_data_schema_models.organizations import Organization

counts = {}


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


def basic_checks(data: dict, type: str) -> dict:
    """Perform basic checks:

    - Check that name is set correctly or set to a default
    - Check that organization is not a string, but an Organization object
    """
    data = upgrade_device(data)
    data = add_name(data, type)
    data = repair_manufacturer(data)

    return data


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    data = basic_checks(data, "Enclosure")

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    data = basic_checks(data, "Objective")

    objective = Objective(
        **data,
    )

    return objective.model_dump()
