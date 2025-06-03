"""Shared utility functions for the AIND Metadata Upgrader."""

from aind_data_schema_models.modalities import Modality

MODALITY_MAP = {
    "SmartSPIM": Modality.SPIM,
}


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
