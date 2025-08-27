"""Base classes for the individual core file upgraders"""

from typing import Optional


class CoreUpgrader:
    """Base class for core file upgraders."""

    def upgrade(self, data: dict, schema_version: str, metadata: Optional[dict] = None) -> dict:  # pragma: no cover
        """Upgrade the core file data to the latest version."""
        raise NotImplementedError("Subclasses must implement this method.")
