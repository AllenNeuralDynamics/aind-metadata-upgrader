"""Base classes for the individual core file upgraders"""


class CoreUpgrader:
    """Base class for core file upgraders."""

    def upgrade(self, data: dict, schema_version: str) -> dict:  # pragma: no cover
        """Upgrade the core file data to the latest version."""
        raise NotImplementedError("Subclasses must implement this method.")
