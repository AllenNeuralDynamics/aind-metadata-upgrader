"""Upgraders for specific devices from v1 to v2."""

from aind_data_schema.components.devices import Enclosure


def _upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()
