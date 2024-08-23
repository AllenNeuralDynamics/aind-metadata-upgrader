"""Module to contain code to upgrade old data description models"""

from copy import deepcopy
from datetime import datetime
from typing import Any, List, Optional, Union

import semver
from aind_data_schema.base import AindModel
from aind_data_schema.core.data_description import (
    DataDescription,
    DataLevel,
    Funding,
)
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.pid_names import PIDName
from aind_data_schema_models.platforms import Platform
from backports.datetime_fromisoformat import MonkeyPatch

from aind_metadata_upgrader.base_upgrade import BaseModelUpgrade
from aind_metadata_upgrader.utils import construct_new_model


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
        elif type(old_modality) in Modality.ALL:
            return old_modality
        else:
            return None


class PlatformUpgrade:
    """Handle upgrades for Platform models."""

    legacy_name_mapping = {
        "smartspim": Platform.SMARTSPIM,
        "single-plane-ophys": Platform.SINGLE_PLANE_OPHYS,
        "hsfp": Platform.HSFP,
        "exaspim": Platform.EXASPIM,
        "ophys": Platform.SINGLE_PLANE_OPHYS,
        "multiplane-ophys": Platform.MULTIPLANE_OPHYS,
        "merfish": Platform.MERFISH,
        "mesospim": Platform.MESOSPIM,
        "spim": Platform.SMARTSPIM,
        "test-fip-opto": Platform.FIP,
        "fip": Platform.FIP,
        "ecephys": Platform.ECEPHYS,
        "behavior-videos": Platform.MULTIPLANE_OPHYS,
        "ephys": Platform.ECEPHYS,
        "trained-behavior": Platform.BEHAVIOR,
    }

    @classmethod
    def from_modality(cls, modality: Modality) -> Optional[Platform]:
        """Get platform from modality"""
        if modality is not None:
            return cls.legacy_name_mapping.get(str.lower(modality.abbreviation))


class FundingUpgrade:
    """Handle upgrades for Funding models."""

    funders_map = {
        "Allen Institute for Brain Science": Organization.AI,
        "Allen Institute for Neural Dynamics": Organization.AI,
        "AIND": Organization.AI,
        "AIBS": Organization.AI,
        "AI": Organization.AI,
        "Allen Institute": Organization.AI,
        Organization.AIND: Organization.AI,
        Organization.AIBS: Organization.AI,
        "NINMH": Organization.NIMH,
        "NIMH": Organization.NIMH,
        "PGA": Organization.AI,
    }

    @classmethod
    def upgrade_funding(cls, old_funding: Any) -> Optional[Funding]:
        """Map legacy Funding model to current version"""
        if type(old_funding) is Funding:
            return old_funding
        elif type(old_funding) is dict and old_funding.get("funder") is not None and type(old_funding["funder"]) is str:
            old_funder_name = old_funding.get("funder")
            new_funding = deepcopy(old_funding)
            if old_funder_name in cls.funders_map.keys():
                new_funding["funder"] = cls.funders_map[old_funder_name]
            return Funding.model_validate(new_funding)
        elif (
            type(old_funding) is dict and old_funding.get("funder") is not None and type(old_funding["funder"]) is dict
        ):
            old_funder_name = old_funding.get("funder")["name"]
            new_funding = deepcopy(old_funding)
            if old_funder_name in cls.funders_map.keys():
                new_funding["funder"] = cls.funders_map[old_funder_name]
            return Funding.model_validate(new_funding)
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


class InvestigatorsUpgrade:
    """Handle upgrades for Investigators field"""

    @staticmethod
    def upgrade_investigators(old_investigators: Any) -> List[PIDName]:
        """Map legacy investigators model to current version"""
        if old_investigators:
            if type(old_investigators) is str:
                return [PIDName(name=old_investigators)]
            elif type(old_investigators) is list and isinstance(old_investigators[0], str):
                return [PIDName(name=inv) for inv in old_investigators]
            elif type(old_investigators) is list and isinstance(old_investigators[0], dict):
                return [PIDName(**inv) for inv in old_investigators]

        return old_investigators


class DataDescriptionUpgrade(BaseModelUpgrade):
    """Handle upgrades for DataDescription class"""

    def __init__(self, old_data_description_dict: Union[dict, AindModel], allow_validation_errors=False):
        """
        Handle mapping of old DataDescription models into current models
        Parameters
        ----------
        old_data_description_dict : DataDescription
        """

        MonkeyPatch.patch_fromisoformat()

        super().__init__(
            old_data_description_dict, model_class=DataDescription, allow_validation_errors=allow_validation_errors
        )

    def get_modality(self, **kwargs):
        """Get modality from old model"""

        old_modality: Any = self.old_model_dict.get("modality")
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

        creation_date = self._get_or_default(self.old_model_dict, "creation_date", kwargs)
        creation_time = self._get_or_default(self.old_model_dict, "creation_time", kwargs)
        old_name = self._get_or_default(self.old_model_dict, "name", kwargs)
        if creation_time:
            if creation_date:
                creation_time = datetime.fromisoformat(f"{creation_date}T{creation_time}")
            else:
                creation_time = datetime.fromisoformat(creation_time)
        elif old_name is not None:
            creation_time = DataDescription.parse_name(old_name).get("creation_time")
        return creation_time

    def upgrade(self, **kwargs) -> AindModel:
        """Upgrades the old model into the current version"""

        version = semver.Version.parse(self._get_or_default(self.old_model_dict, "schema_version", kwargs))

        institution = InstitutionUpgrade.upgrade_institution(
            self._get_or_default(self.old_model_dict, "institution", kwargs)
        )

        funding_source = self._get_or_default(self.old_model_dict, "funding_source", kwargs)

        funding_source = FundingUpgrade.upgrade_funding_source(funding_source=funding_source)

        modality = self.get_modality(**kwargs)

        data_level = self._get_or_default(self.old_model_dict, "data_level", kwargs)
        if data_level in ["raw level", "raw data"]:
            data_level = DataLevel.RAW
        if data_level in ["derived level", "derived data"]:
            data_level = DataLevel.DERIVED

        experiment_type = self._get_or_default(self.old_model_dict, "experiment_type", kwargs)
        platform = None
        if experiment_type is not None:
            for p in Platform.ALL:
                if p().abbreviation == experiment_type:
                    platform = p()
                    break

        if platform is None:
            platform = self._get_or_default(self.old_model_dict, "platform", kwargs)
            if platform is None and version <= "0.8.0":
                if type(modality) is list:
                    platform = PlatformUpgrade.from_modality(modality[0])

        investigators = self._get_or_default(self.old_model_dict, "investigators", kwargs)
        investigators = InvestigatorsUpgrade.upgrade_investigators(investigators)

        creation_time = self.get_creation_time(**kwargs)

        data_desc_dict = {
            "creation_time": creation_time,
            "name": self._get_or_default(self.old_model_dict, "name", kwargs),
            "institution": institution,
            "funding_source": funding_source,
            "data_level": data_level,
            "group": self._get_or_default(self.old_model_dict, "group", kwargs),
            "investigators": investigators,
            "project_name": self._get_or_default(self.old_model_dict, "project_name", kwargs),
            "restrictions": self._get_or_default(self.old_model_dict, "restrictions", kwargs),
            "modality": modality,
            "platform": platform,
            "subject_id": self._get_or_default(self.old_model_dict, "subject_id", kwargs),
            "related_data": self._get_or_default(self.old_model_dict, "related_data", kwargs),
            "data_summary": self._get_or_default(self.old_model_dict, "data_summary", kwargs),
        }

        return construct_new_model(data_desc_dict, DataDescription, self.allow_validation_errors)
