"""Tests methods for upgrading DataDescriptions"""

import copy
import datetime
import json
import os
import re
import unittest
from pathlib import Path
from typing import List

from aind_data_schema.core.data_description import (
    DataDescription,
    DataLevel,
    Funding,
    Group,
    RelatedData,
)
from aind_data_schema_models.modalities import Modality
from aind_data_schema_models.organizations import Organization
from aind_data_schema_models.pid_names import PIDName
from aind_data_schema_models.platforms import Platform
from pydantic import ValidationError
from pydantic import __version__ as pyd_version
from tzlocal import get_localzone

from aind_metadata_upgrader.data_description_upgrade import (
    DataDescriptionUpgrade,
    FundingUpgrade,
    InstitutionUpgrade,
    InvestigatorsUpgrade,
    ModalityUpgrade,
)

DATA_DESCRIPTION_FILES_PATH = Path(__file__).parent / "resources" / "ephys_data_description"
PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)
TZLOCAL = get_localzone()


class TestDataDescriptionUpgrade(unittest.TestCase):
    """Tests methods in DataDescriptionUpgrade class"""

    @classmethod
    def setUpClass(cls):
        """Load json files before running tests."""
        data_description_files: List[str] = os.listdir(DATA_DESCRIPTION_FILES_PATH)
        data_descriptions = []
        for file_path in data_description_files:
            with open(DATA_DESCRIPTION_FILES_PATH / file_path) as f:
                contents = json.load(f)
            data_descriptions.append((file_path, contents))
        cls.data_descriptions = dict(data_descriptions)

    def test_upgrades_0_3_0(self):
        """Tests data_description_0.3.0.json is mapped correctly."""
        data_description_0_3_0 = self.data_descriptions["data_description_0.3.0.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_3_0)

        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2022, 6, 28, 10, 31, 30, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_623705_2022-06-28_10-31-30", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("623705", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertIsNone(new_data_description.data_summary)

    def test_upgrades_0_3_0_wrong_field(self):
        """Tests data_description_0.3.0_wrong_field.json is mapped correctly."""
        data_description_0_3_0 = self.data_descriptions["data_description_0.3.0_wrong_field.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_3_0)

        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2022, 7, 26, 10, 52, 15, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_624643_2022-07-26_10-52-15", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("624643", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertIsNone(new_data_description.data_summary)

        # Should also work by inputting legacy
        new_data_description2 = upgrader.upgrade(platform=Platform.ECEPHYS, data_level="raw level")
        self.assertEqual(DataLevel.RAW, new_data_description2.data_level)

        # Should fail if inputting unknown string
        with self.assertRaises(Exception) as e1:
            upgrader.upgrade(platform=Platform.ECEPHYS, data_level="asfnewnjfq")

        expected_error_message1 = (
            "1 validation error for DataDescription\n"
            "data_level\n"
            "  Input should be 'derived', 'raw' or 'simulated' [type=enum, input_value='asfnewnjfq', input_type=str]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/enum"
        )

        self.assertEqual(expected_error_message1, repr(e1.exception))

        # Should also fail if inputting wrong type
        with self.assertRaises(Exception) as e2:
            upgrader.upgrade(platform=Platform.ECEPHYS, data_level=["raw"])
        expected_error_message2 = (
            "1 validation error for DataDescription\n"
            "data_level\n"
            "  Input should be 'derived', 'raw' or 'simulated' [type=enum, input_value=['raw'], input_type=list]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/enum"
        )

        self.assertEqual(expected_error_message2, repr(e2.exception))

        # Should work if data_level is missing in original json doc and
        # user sets it explicitly
        data_description_copy = copy.deepcopy(data_description_0_3_0)
        del data_description_copy["data_level"]
        upgrader3 = DataDescriptionUpgrade(old_data_description_dict=data_description_copy)
        new_data_description3 = upgrader3.upgrade(platform=Platform.ECEPHYS, data_level=DataLevel.DERIVED)
        self.assertEqual(DataLevel.DERIVED, new_data_description3.data_level)

    def test_upgrades_0_3_0_missing_creation_time(self):
        """Tests upgrade with missing creation time"""

        data_description_0_3_0_missing_creation_time = self.data_descriptions["data_description_0.3.0_no_creation.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_3_0_missing_creation_time)

        new_data_description = upgrader.upgrade(platform=Platform.ECEPHYS, data_level=DataLevel.RAW)

        self.assertEqual(new_data_description.creation_time, datetime.datetime(2022, 6, 28, 10, 31, 30, tzinfo=TZLOCAL))

    def test_upgrades_0_4_0(self):
        """Tests data_description_0.4.0.json is mapped correctly."""
        data_description_0_4_0 = self.data_descriptions["data_description_0.4.0.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_4_0)

        # Should work by setting platform explicitly
        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2023, 4, 13, 14, 35, 51, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_664438_2023-04-13_14-35-51", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("664438", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertIsNone(new_data_description.data_summary)

    def test_upgrades_0_6_0(self):
        """Tests data_description_0.6.0.json is mapped correctly."""
        data_description_0_6_0 = self.data_descriptions["data_description_0.6.0.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_6_0)

        # Should work by setting experiment type explicitly
        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2023, 4, 10, 17, 9, 26, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_661278_2023-04-10_17-09-26", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("661278", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertIsNone(new_data_description.data_summary)

    def test_upgrades_0_6_2(self):
        """Tests data_description_0.6.2.json is mapped correctly."""
        data_description_0_6_2 = self.data_descriptions["data_description_0.6.2.json"]
        data_description_0_6_2_copy = copy.deepcopy(data_description_0_6_2)
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_6_2)

        # Should work by setting experiment type explicitly
        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2023, 3, 23, 22, 31, 18, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("661279_2023-03-23_15-31-18", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertEqual(Group.EPHYS, new_data_description.group)
        self.assertEqual([PIDName(name="John Doe"), PIDName(name="Mary Smith")], new_data_description.investigators)
        self.assertEqual("mri-guided-electrophysiology", new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("661279", new_data_description.subject_id)
        self.assertEqual(
            [
                RelatedData(
                    related_data_path="\\\\allen\\aind\\scratch\\ephys\\persist\\data\\MRI\\processed\\661279",
                    relation="Contains MRI and processing used to choose insertion locations.",
                )
            ],
            new_data_description.related_data,
        )
        self.assertEqual(
            (
                "This dataset was collected to evaluate the accuracy and feasibility "
                "of the AIND MRI-guided insertion pipeline. "
                "One probe targets the retinotopic center of LGN, with drifting grating for "
                "receptive field mapping to evaluate targeting. "
                "Other targets can be evaluated in histology."
            ),
            new_data_description.data_summary,
        )

        # Testing a few edge cases
        new_dd_0_6_2 = upgrader.upgrade(modality=[Modality.ECEPHYS])
        self.assertEqual([Modality.ECEPHYS], new_dd_0_6_2.modality)
        # Blank Modality
        data_description_0_6_2_copy["modality"] = None
        upgrader2 = DataDescriptionUpgrade(old_data_description_dict=data_description_0_6_2_copy)
        with self.assertRaises(Exception) as e:
            upgrader2.upgrade()

        expected_error_message = "ValueError('Unable to upgrade modality: None')"
        self.assertEqual(expected_error_message, repr(e.exception))

    def test_upgrades_0_6_2_wrong_field(self):
        """Tests data_description_0.6.2_wrong_field.json is mapped correctly."""
        data_description_0_6_2_wrong_field = self.data_descriptions["data_description_0.6.2_wrong_field.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_6_2_wrong_field)

        # Should complain about funder not being correct
        with self.assertRaises(Exception) as e:
            upgrader.upgrade()

        expected_error_message = "1 validation error for Funding"
        self.assertIn(expected_error_message, repr(e.exception))

        # Should work by setting funding_source explicitly
        new_data_description = upgrader.upgrade(funding_source=[Funding(funder=Organization.AI)])

        self.assertEqual(
            datetime.datetime(2023, 3, 23, 22, 31, 18, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("661279_2023-03-23_15-31-18", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertEqual(Group.EPHYS, new_data_description.group)
        self.assertEqual([PIDName(name="John Doe"), PIDName(name="Mary Smith")], new_data_description.investigators)
        self.assertEqual("mri-guided-electrophysiology", new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("661279", new_data_description.subject_id)
        self.assertEqual(
            [
                RelatedData(
                    related_data_path="\\\\allen\\aind\\scratch\\ephys\\persist\\data\\MRI\\processed\\661279",
                    relation="Contains MRI and processing used to choose insertion locations.",
                )
            ],
            new_data_description.related_data,
        )
        self.assertEqual(
            (
                "This dataset was collected to evaluate the accuracy and feasibility "
                "of the AIND MRI-guided insertion pipeline. "
                "One probe targets the retinotopic center of LGN, with drifting grating for "
                "receptive field mapping to evaluate targeting. "
                "Other targets can be evaluated in histology."
            ),
            new_data_description.data_summary,
        )

    def test_upgrades_0_6_2_missing_investigators(self):
        """Tests upgrade with missing investigators"""

        data_description_0_6_2_missing_investigators = self.data_descriptions[
            "data_description_0.6.2_empty_investigators.json"
        ]
        upgrader = DataDescriptionUpgrade(
            old_data_description_dict=data_description_0_6_2_missing_investigators, allow_validation_errors=True
        )

        new_data_description = upgrader.upgrade()

        self.assertEqual(new_data_description.investigators, [])

    def test_upgrades_0_10_0(self):
        """Tests data_description_0.10.0.json is mapped correctly."""
        data_description_0_10_0 = self.data_descriptions["data_description_0.10.0.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_10_0)

        # Should work by setting experiment type explicitly
        new_data_description = upgrader.upgrade()
        self.assertEqual(
            datetime.datetime(2023, 10, 18, 16, 00, 6, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_691897_2023-10-18_16-00-06", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("691897", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertEqual(Platform.ECEPHYS, new_data_description.platform)
        self.assertIsNone(new_data_description.data_summary)

    def test_upgrades_0_11_0_wrong_funding(self):
        """Tests data_description_0.11.0.json is mapped correctly."""
        data_description_0_11_0 = self.data_descriptions["data_description_0.11.0_wrong_funder.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_11_0)

        new_data_description = upgrader.upgrade()
        # AIND should be set to AI by upgrader
        self.assertEqual(
            [Funding(funder=Organization.AI)],
            new_data_description.funding_source,
        )
        self.assertEqual(
            datetime.datetime(2023, 3, 6, 15, 8, 24, tzinfo=TZLOCAL),
            new_data_description.creation_time,
        )
        self.assertEqual("ecephys_649038_2023-03-06_15-08-24", new_data_description.name)
        self.assertEqual(Organization.AIND, new_data_description.institution)
        self.assertEqual(DataLevel.RAW, new_data_description.data_level)
        self.assertIsNone(new_data_description.group)
        self.assertEqual([PIDName(name="John Doe")], new_data_description.investigators)
        self.assertIsNone(new_data_description.project_name)
        self.assertIsNone(new_data_description.restrictions)
        self.assertEqual([Modality.ECEPHYS], new_data_description.modality)
        self.assertEqual("649038", new_data_description.subject_id)
        self.assertEqual([], new_data_description.related_data)
        self.assertEqual(Platform.ECEPHYS, new_data_description.platform)
        self.assertIsNone(new_data_description.data_summary)

    def test_upgrades_creation_time(self):
        """Tests that strings which include a Z timezone are upgraded correctly"""

        data_description_0_13_8 = self.data_descriptions["data_description_0.13.8_parse_time.json"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_13_8)

        new_data_description = upgrader.upgrade()

        self.assertEqual(
            datetime.datetime(2024, 6, 11, 18, 37, 31, microsecond=983373, tzinfo=datetime.timezone.utc),
            new_data_description.creation_time,
        )

    def test_data_level_upgrade(self):
        """Tests data level can be set from legacy versions"""

        d1 = DataDescription(
            label="test_data",
            modality=[Modality.SPIM],
            platform=Platform.EXASPIM,
            subject_id="1234",
            data_level="raw",
            creation_time=datetime.datetime(2020, 10, 10, 10, 10, 10),
            institution=Organization.AIND,
            funding_source=[Funding(funder=Organization.NINDS, grant_number="grant001")],
            investigators=[PIDName(name="Jane Smith")],
        )
        d2 = DataDescription(
            label="test_data",
            modality=[Modality.SPIM],
            platform=Platform.EXASPIM,
            subject_id="1234",
            data_level=DataLevel.RAW,
            creation_time=datetime.datetime(2020, 10, 10, 10, 10, 10),
            institution=Organization.AIND,
            funding_source=[Funding(funder=Organization.NINDS, grant_number="grant001")],
            investigators=[PIDName(name="Jane Smith")],
        )
        with self.assertRaises(ValidationError) as e:
            DataDescription(
                label="test_data",
                modality=[Modality.SPIM],
                platform=Platform.EXASPIM,
                subject_id="1234",
                data_level=[2, 3],
                creation_time=datetime.datetime(2020, 10, 10, 10, 10, 10),
                institution=Organization.AIND,
                funding_source=[Funding(funder=Organization.NINDS, grant_number="grant001")],
                investigators=[PIDName(name="Jane Smith")],
            )
        expected_error_message = (
            "1 validation error for DataDescription\n"
            "data_level\n"
            "  Input should be 'derived', 'raw' or 'simulated' [type=enum, input_value=[2, 3], input_type=list]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/enum"
        )
        self.assertEqual(
            expected_error_message,
            repr(e.exception),
        )

        # this no longer throws the expected exception
        self.assertEqual(DataLevel.RAW, d1.data_level)
        self.assertEqual(DataLevel.RAW, d2.data_level)

    # def test_edge_cases(self):
    #     """Tests a few edge cases"""
    #     data_description_0_6_2 = deepcopy(self.data_descriptions["data_description_0.6.2.json"])
    #     upgrader = DataDescriptionUpgrade(old_data_description_dict=data_description_0_6_2)
    #     new_dd_0_6_2 = upgrader.upgrade(modality=[Modality.ECEPHYS])
    #     self.assertEqual([Modality.ECEPHYS], new_dd_0_6_2.modality)


class TestModalityUpgrade(unittest.TestCase):
    """Tests ModalityUpgrade methods"""

    def test_modality_upgrade(self):
        """Tests edge case"""
        self.assertIsNone(ModalityUpgrade.upgrade_modality(None))
        self.assertEqual(
            Modality.ECEPHYS,
            ModalityUpgrade.upgrade_modality(Modality.ECEPHYS),
        )
        self.assertEqual(Modality.ICEPHYS, ModalityUpgrade.upgrade_modality("icephys"))

    def test_modality_lookup(self):
        """Tests old modality lookup case"""

        dd_dict = {
            "describedBy": "https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema"
            "/main/src/aind_data_schema/data_description.py",
            "schema_version": "0.3.0",
            "license": "CC-BY-4.0",
            "creation_time": "16:01:12.123456",
            "creation_date": "2022-11-01",
            "name": "SmartSPIM_623711_2022-10-27_16-48-54_stitched_2022-11-01_16-01-12",
            "institution": "AIND",
            "investigators": ["John Doe"],
            "funding_source": [{"funder": "AIND", "grant_number": None, "fundee": None}],
            "data_level": "derived data",
            "group": None,
            "project_name": None,
            "project_id": None,
            "restrictions": None,
            "modality": "SmartSPIM",
            "platform": Platform.SMARTSPIM,
            "subject_id": "623711",
            "input_data_name": "SmartSPIM_623711_2022-10-27_16-48-54",
        }
        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        upgrader.upgrade()


class TestPlatformUpgrade(unittest.TestCase):
    """Tests PlatformUpgrade methods"""

    def test_platform_upgrade(self):
        """Tests edge case"""

        dd_dict = {
            "describedBy": "https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema"
            "/main/src/aind_data_schema/data_description.py",
            "schema_version": "0.3.0",
            "license": "CC-BY-4.0",
            "creation_time": "16:01:12.123456",
            "creation_date": "2022-11-01",
            "name": "SmartSPIM_623711_2022-10-27_16-48-54_stitched_2022-11-01_16-01-12",
            "institution": "AIND",
            "investigators": ["John Doe"],
            "funding_source": [{"funder": "AI", "grant_number": None, "fundee": None}],
            "data_level": "derived data",
            "group": None,
            "project_name": None,
            "project_id": None,
            "restrictions": None,
            "modality": "SmartSPIM",
            "platform": None,
            "subject_id": "623711",
            "input_data_name": "SmartSPIM_623711_2022-10-27_16-48-54",
        }

        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        upgrader.upgrade()

    def test_platform_lookup(self):
        """Tests old platform lookup case"""
        dd_dict = {
            "describedBy": "https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema"
            "/main/src/aind_data_schema/data_description.py",
            "schema_version": "0.3.0",
            "license": "CC-BY-4.0",
            "creation_time": "16:01:12.123456",
            "creation_date": "2022-11-01",
            "name": "SmartSPIM_623711_2022-10-27_16-48-54_stitched_2022-11-01_16-01-12",
            "institution": "AIND",
            "investigators": ["John Doe"],
            "funding_source": [{"funder": "AI", "grant_number": None, "fundee": None}],
            "data_level": "derived data",
            "group": None,
            "project_name": None,
            "project_id": None,
            "restrictions": None,
            "modality": "ecephys",
            "platform": None,
            "subject_id": "623711",
            "input_data_name": "SmartSPIM_623711_2022-10-27_16-48-54",
        }
        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        upgrader.upgrade()


class TestFundingUpgrade(unittest.TestCase):
    """Tests FundingUpgrade methods"""

    def test_funding_upgrade(self):
        """Tests edge case"""

        # Default gets set to AI
        self.assertEqual(
            Funding(funder=Organization.AI, grant_number=None, fundee=None),
            FundingUpgrade.upgrade_funding(None),
        )

        # Check static method edge case:
        self.assertEqual([], FundingUpgrade.upgrade_funding_source(None))

        self.assertEqual(
            Funding(funder=Organization.AI),
            FundingUpgrade.upgrade_funding(
                {
                    "funder": {
                        "name": "Allen Institute",
                        "abbreviation": "AI",
                        "registry": {
                            "name": "Research Organization Registry",
                            "abbreviation": "ROR",
                        },
                        "registry_identifier": "03cpe7c52",
                    },
                    "grant_number": None,
                    "fundee": None,
                }
            ),
        )

    def test_funding_lookup(self):
        """Tests old funding lookup case"""
        dd_dict = {
            "describedBy": "https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema"
            "/main/src/aind_data_schema/data_description.py",
            "schema_version": "0.3.0",
            "license": "CC-BY-4.0",
            "creation_time": "16:01:12.123456",
            "creation_date": "2022-11-01",
            "name": "SmartSPIM_623711_2022-10-27_16-48-54_stitched_2022-11-01_16-01-12",
            "institution": "AIND",
            "investigators": ["John Doe"],
            "funding_source": [
                {
                    "funder": {
                        "name": "Allen Institute",
                        "abbreviation": "AI",
                        "registry": {
                            "name": "Research Organization Registry",
                            "abbreviation": "ROR",
                        },
                        "registry_identifier": "03cpe7c52",
                    },
                    "grant_number": None,
                    "fundee": None,
                }
            ],
            "data_level": "derived data",
            "group": None,
            "project_name": None,
            "project_id": None,
            "restrictions": None,
            "modality": "SmartSPIM",
            "platform": Platform.SMARTSPIM,
            "subject_id": "623711",
            "input_data_name": "SmartSPIM_623711_2022-10-27_16-48-54",
        }
        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        upgrader.upgrade()

        self.assertEqual(dd_dict["funding_source"], [Funding(funder=Organization.AI).model_dump()])

        dd_dict["funding_source"] = [{"funder": Organization.AIND, "grant_number": None, "fundee": None}]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        dd2 = upgrader.upgrade()

        self.assertEqual(dd2.funding_source, [Funding(funder=Organization.AI)])

        dd_dict["funding_source"] = ["Allen Institute for Neural Dynamics"]
        upgrader = DataDescriptionUpgrade(old_data_description_dict=dd_dict)
        dd3 = upgrader.upgrade()

        self.assertEqual(dd3.funding_source, [Funding(funder=Organization.AI)])


class TestInstitutionUpgrade(unittest.TestCase):
    """Tests InstitutionUpgrade methods"""

    def test_institution_upgrade(self):
        """Tests edge case"""
        self.assertIsNone(InstitutionUpgrade.upgrade_institution(None))


class TestInvestigatorsUpgrade(unittest.TestCase):
    """Tests InvestigatorsUpgrade methods"""

    def test_investigators_upgrade(self):
        """Tests edge case"""
        self.assertEqual(InvestigatorsUpgrade.upgrade_investigators(["John Doe"]), [PIDName(name="John Doe")])
        self.assertEqual(
            InvestigatorsUpgrade.upgrade_investigators([PIDName(name="John Doe")]), [PIDName(name="John Doe")]
        )
        self.assertEqual(InvestigatorsUpgrade.upgrade_investigators("John Doe"), [PIDName(name="John Doe")])
        self.assertEqual(
            InvestigatorsUpgrade.upgrade_investigators([dict(name="John Doe")]), [PIDName(name="John Doe")]
        )


if __name__ == "__main__":
    unittest.main()
