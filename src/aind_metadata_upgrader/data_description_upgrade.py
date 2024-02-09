"""Module to contain code to upgrade old data description models"""

from copy import deepcopy
from datetime import datetime
from typing import Any, Optional, Union

import semver

from aind_data_schema.base import AindModel
from aind_data_schema.core.data_description import (
    DataDescription,
    DataLevel,
    Funding,
)
from aind_data_schema.models.modalities import Modality
from aind_data_schema.models.organizations import Organization
from aind_data_schema.models.platforms import Platform

from aind_metadata_upgrader.base_upgrade import BaseModelUpgrade


class ModalityUpgrade:
    """Handle upgrades for Modality models."""

    legacy_name_mapping = {
        "exaspim": Modality.SPIM,
        "smartspim": Modality.SPIM,
        "ecephys": Modality.ECEPHYS,
        "mri-14t": Modality.MRI,
        "mri-7t": Modality.MRI,
        "test-fip-opto": Modality.FIB,
        "hsfp": Modality.FIB,
        "fip": Modality.FIB,
        "merfish": Modality.MERFISH,
        "dispim": Modality.SPIM,
        "mesospim": Modality.SPIM,
        "single-plane-ophys": Modality.POPHYS,
        "multiplane-ophys": Modality.POPHYS,
    }

    @classmethod
    def upgrade_modality(cls, old_modality: Union[str, dict, Modality, None]) -> Optional[Modality]:
        """
        Converts old modality models into the current model.
        Parameters
        ----------
        old_modality : Union[str, dict, Modality, None]
          Old models may consist of strings or dictionaries.

        Returns
        -------
        Modality
          Will raise a validation error if unable to parse old modalities.

        """
        if type(old_modality) is str and cls.legacy_name_mapping.get(old_modality.lower()) is not None:
            return cls.legacy_name_mapping[old_modality.lower()]
        elif type(old_modality) is str:
            return Modality.from_abbreviation(old_modality)
        elif type(old_modality) is dict and old_modality.get("abbreviation") is not None:
            return Modality.from_abbreviation(old_modality["abbreviation"])
        elif type(old_modality) in Modality._ALL:
            return old_modality
        else:
            return None


class PlatformUpgrade:
    """Handle upgrades for Platform models."""

    legacy_name_mapping = {
        'trained-behavior': Platform.BEHAVIOR,
        'smartspim': Platform.SMARTSPIM,
        'single-plane-ophys': Platform.SINGLE_PLANE_OPHYS,
        'HSFP': Platform.HSFP,
        'exaSPIM': Platform.EXASPIM,
        'ophys': Platform.SINGLE_PLANE_OPHYS,
        'multiplane-ophys': Platform.MULTIPLANE_OPHYS,
        'merfish': Platform.MERFISH,
        'mesoSPIM': Platform.MESOSPIM,
        'SPIM': Platform.SMARTSPIM,
        'test-FIP-opto': Platform.FIP,
        'confocal': Platform.CONFOCAL,
        'FIP': Platform.FIP,
        'ecephys': Platform.ECEPHYS,
        'behavior-videos': Platform.BEHAVIOR,
        'SmartSPIM': Platform.SMARTSPIM,
        'ephys': Platform.ECEPHYS
    }

    @classmethod
    def from_modality(cls, modality: Modality) -> Optional[Platform]:
        """Get platform from modality"""
        if modality is not None:
            return cls.legacy_name_mapping.get(modality.abbreviation)
            

class FundingUpgrade:
    """Handle upgrades for Funding models."""

    @staticmethod
    def upgrade_funding(old_funding: Any) -> Optional[Funding]:
        """Map legacy Funding model to current version"""
        if type(old_funding) is Funding:
            return old_funding
        elif type(old_funding) is dict and old_funding.get("funder") is not None and type(old_funding["funder"]) is str:
            old_funder = old_funding.get("funder")
            if Organization().name_map.get(old_funder) is not None:
                new_funder = Organization.from_name(old_funder)
            else:
                new_funder = Organization.from_abbreviation(old_funder)
            new_funding = deepcopy(old_funding)
            new_funding["funder"] = new_funder
            return Funding.model_validate(new_funding)
        elif (
            type(old_funding) is dict and old_funding.get("funder") is not None and type(old_funding["funder"]) is dict
        ):
            return Funding.model_validate(old_funding)
        else:
            return Funding(funder=Organization.AI)

    @staticmethod
    def upgrade_funding_source(funding_source):
        """Get funding source from old model"""
        if funding_source is not None:
            if type(funding_source) is list:
                funding_source = [FundingUpgrade.upgrade_funding(funding) for funding in funding_source]
        else:
            funding_source = []

        return funding_source


class InstitutionUpgrade:
    """Handle upgrades for Institution class"""

    @staticmethod
    def upgrade_institution(old_institution: Any) -> Optional[Organization]:
        """Map legacy Institution model to current version"""
        if type(old_institution) is str:
            return Organization.from_abbreviation(old_institution)
        elif type(old_institution) is dict and old_institution.get("abbreviation") is not None:
            return Organization.from_abbreviation(old_institution.get("abbreviation"))
        else:
            return None


class DataDescriptionUpgrade(BaseModelUpgrade):
    """Handle upgrades for DataDescription class"""

    def __init__(self, old_data_description_model: DataDescription):
        """
        Handle mapping of old DataDescription models into current models
        Parameters
        ----------
        old_data_description_model : DataDescription
        """
        super().__init__(old_data_description_model, model_class=DataDescription)

    def get_modality(self, **kwargs):
        """Get modality from old model"""

        old_modality: Any = self.old_model.modality
        if kwargs.get("modality") is not None:
            modality = kwargs["modality"]
        elif type(old_modality) is str or type(old_modality) is dict:
            modality = [ModalityUpgrade.upgrade_modality(old_modality)]
        elif type(old_modality) is list:
            modality = [ModalityUpgrade.upgrade_modality(m) for m in old_modality]
        else:
            raise ValueError(f"Unable to upgrade modality: {old_modality}")

        return modality

    def get_creation_time(self, **kwargs):
        """Get creation time from old model"""

        creation_date = self._get_or_default(self.old_model, "creation_date", kwargs)
        creation_time = self._get_or_default(self.old_model, "creation_time", kwargs)
        old_name = self._get_or_default(self.old_model, "name", kwargs)
        if creation_date is not None and creation_time is not None:
            creation_time = datetime.fromisoformat(f"{creation_date}T{creation_time}")
        elif creation_time is not None:
            creation_time = datetime.fromisoformat(f"{creation_time}")
        elif old_name is not None:
            creation_time = DataDescription.parse_name(old_name).get("creation_time")
        return creation_time

    def upgrade(self, **kwargs) -> AindModel:
        """Upgrades the old model into the current version"""

        version = semver.Version.parse(self._get_or_default(self.old_model, "schema_version", kwargs))

        institution = InstitutionUpgrade.upgrade_institution(
            self._get_or_default(self.old_model, "institution", kwargs)
        )

        funding_source = self._get_or_default(self.old_model, "funding_source", kwargs)

        funding_source = FundingUpgrade.upgrade_funding_source(funding_source=funding_source)

        modality = self.get_modality(**kwargs)

        data_level = self._get_or_default(self.old_model, "data_level", kwargs)
        if data_level in ["raw level", "raw data"]:
            data_level = DataLevel.RAW
        if data_level in ["derived level", "derived data"]:
            data_level = DataLevel.DERIVED

        experiment_type = self._get_or_default(self.old_model, "experiment_type", kwargs)
        platform = None
        if experiment_type is not None:
            for p in Platform._ALL:
                if p().abbreviation == experiment_type:
                    platform = p()
                    break

        if platform is None:
            platform = self._get_or_default(self.old_model, "platform", kwargs)
            if platform is None and version <= "0.8.0":
                if type(modality) is list:
                    platform = PlatformUpgrade.from_modality(modality[0])
                elif type(modality) is str:
                    platform = PlatformUpgrade.from_modality(modality)


        creation_time = self.get_creation_time(**kwargs)

        return DataDescription(
            creation_time=creation_time,
            name=self._get_or_default(self.old_model, "name", kwargs),
            institution=institution,
            funding_source=funding_source,
            data_level=data_level,
            group=self._get_or_default(self.old_model, "group", kwargs),
            investigators=self._get_or_default(self.old_model, "investigators", kwargs),
            project_name=self._get_or_default(self.old_model, "project_name", kwargs),
            restrictions=self._get_or_default(self.old_model, "restrictions", kwargs),
            modality=modality,
            platform=platform,
            subject_id=self._get_or_default(self.old_model, "subject_id", kwargs),
            related_data=self._get_or_default(self.old_model, "related_data", kwargs),
            data_summary=self._get_or_default(self.old_model, "data_summary", kwargs),
        )
