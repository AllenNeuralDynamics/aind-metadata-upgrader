"""Upgraders for specific devices from v1 to v2."""

from aind_data_schema.components.devices import (
    Enclosure,
    Objective,
)


def upgrade_enclosure(data: dict) -> dict:
    """Upgrade enclosure data to the new model."""

    enclosure = Enclosure(
        **data,
    )

    return enclosure.model_dump()


def upgrade_objective(data: dict) -> dict:
    """Upgrade objective data to the new model."""

    objective = Objective(
        **data,
    )

    return objective.model_dump()
