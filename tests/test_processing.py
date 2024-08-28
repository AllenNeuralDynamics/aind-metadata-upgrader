""" tests for Processing upgrades """

import datetime
import json
import os
import re
import unittest
from pathlib import Path
from typing import List

from aind_data_schema.base import AindGeneric
from aind_data_schema.core.processing import (
    DataProcess,
    PipelineProcess,
    Processing,
)
from pydantic import __version__ as pyd_version

from aind_metadata_upgrader.processing_upgrade import (
    DataProcessUpgrade,
    ProcessingUpgrade,
)

PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)

PROCESSING_FILES_PATH = Path(__file__).parent / "resources" / "ephys_processing"
PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)


class TestProcessingUpgrade(unittest.TestCase):
    """Tests methods in ProcessingUpgrade class"""

    @classmethod
    def setUpClass(cls):
        """Load json files before running tests."""
        processing_files: List[str] = os.listdir(PROCESSING_FILES_PATH)
        processings = []
        for file_path in processing_files:
            with open(PROCESSING_FILES_PATH / file_path) as f:
                contents = json.load(f)
            processings.append((file_path, contents))
        cls.processings = dict(processings)

    def test_upgrades_0_0_1(self):
        """Tests processing_0.0.1.json is mapped correctly."""
        processing_0_0_1 = self.processings["processing_0.0.1.json"]
        upgrader = ProcessingUpgrade(old_processing_model=processing_0_0_1)
        # Should complain about processor_full_name being None
        with self.assertRaises(Exception) as e:
            upgrader.upgrade()

        expected_error_message = (
            "1 validation error for PipelineProcess\n"
            "processor_full_name\n"
            "  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/string_type"
        )

        self.assertEqual(expected_error_message, repr(e.exception))

        # Should work by setting platform explicitly
        new_processing = upgrader.upgrade(processor_full_name="Unit Test")
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "Unit Test")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Ephys preprocessing")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.1.5")
        self.assertEqual(
            ephys_preprocessing_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
            "0.1.5",
        )
        self.assertEqual(ephys_preprocessing_process.software_version, "0.1.5")

    def test_upgrades_0_1_0(self):
        """Tests processing_0.1.0.json is mapped correctly."""
        processing_0_1_0 = self.processings["processing_0.1.0.json"]
        upgrader = ProcessingUpgrade(old_processing_model=processing_0_1_0)
        # Should complain about processor_full_name being None
        with self.assertRaises(Exception) as e:
            upgrader.upgrade()

        expected_error_message = (
            "1 validation error for PipelineProcess\n"
            "processor_full_name\n"
            "  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/string_type"
        )
        self.assertEqual(expected_error_message, repr(e.exception))

        # Should work by setting platform explicitly
        new_processing = upgrader.upgrade(processor_full_name="Unit Test")
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "Unit Test")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Ephys preprocessing")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.5.0")
        self.assertEqual(
            ephys_preprocessing_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
        )

    def test_upgrades_0_2_1(self):
        """Tests processing_0.2.1.json is mapped correctly."""
        processing_0_2_1 = self.processings["processing_0.2.1.json"]
        upgrader = ProcessingUpgrade(old_processing_model=processing_0_2_1)
        # Should complain about processor_full_name being None
        with self.assertRaises(Exception) as e:
            upgrader.upgrade()

        expected_error_message = (
            "1 validation error for PipelineProcess\n"
            "processor_full_name\n"
            "  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/string_type"
        )
        self.assertEqual(expected_error_message, repr(e.exception))

        # Should work by setting platform explicitly
        new_processing = upgrader.upgrade(processor_full_name="Unit Test")
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "Unit Test")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Ephys preprocessing")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.16.2")
        self.assertEqual(
            ephys_preprocessing_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
        )

    def test_upgrades_0_2_5(self):
        """Tests processing_0.1.0.json is mapped correctly."""
        processing_0_2_5 = self.processings["processing_0.2.5.json"]
        upgrader = ProcessingUpgrade(old_processing_model=processing_0_2_5)
        # Should complain about processor_full_name being None
        with self.assertRaises(Exception) as e:
            upgrader.upgrade()

        expected_error_message = (
            "1 validation error for PipelineProcess\n"
            "processor_full_name\n"
            "  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]\n"
            f"    For further information visit https://errors.pydantic.dev/{PYD_VERSION}/v/string_type"
        )
        self.assertEqual(expected_error_message, repr(e.exception))

        # Should work by setting platform explicitly
        new_processing = upgrader.upgrade(processor_full_name="Unit Test")
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "Unit Test")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Ephys preprocessing")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.29.3")
        self.assertEqual(
            ephys_preprocessing_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
        )

    def test_upgrades_0_3_1(self):
        """Tests processing_0.3.1.json is mapped correctly."""
        processing_0_3_1 = self.processings["processing_0.3.1.json"]
        upgrader = ProcessingUpgrade(old_processing_model=processing_0_3_1)

        # Should work by setting platform explicitly
        new_processing = upgrader.upgrade()
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "service")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Compression")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.32.0")
        self.assertEqual(
            ephys_preprocessing_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
        )

    def test_upgrades_current(self):
        """Tests processing_0.1.0.json is mapped correctly."""
        datetime_now = datetime.datetime.now()

        data_process = DataProcess(
            name="Ephys preprocessing",
            software_version="0.1000.0",
            code_url="my-code-repo",
            start_date_time=datetime_now,
            end_date_time=datetime_now,
            input_location="my-input-location",
            output_location="my-output-location",
            parameters={"param1": "value1"},
        )
        processing_pipeline = PipelineProcess(
            data_processes=[data_process],
            pipeline_url="my-pipeline-url",
            pipeline_version="0.1.0",
            processor_full_name="Unit Test",
        )
        current_processing = Processing(
            processing_pipeline=processing_pipeline,
        )

        upgrader = ProcessingUpgrade(old_processing_model=current_processing)
        new_processing = upgrader.upgrade()
        processing_pipeline = new_processing.processing_pipeline
        self.assertEqual(processing_pipeline.processor_full_name, "Unit Test")
        self.assertEqual(processing_pipeline.pipeline_url, "my-pipeline-url")
        self.assertEqual(processing_pipeline.pipeline_version, "0.1.0")
        ephys_preprocessing_process = processing_pipeline.data_processes[0]
        self.assertEqual(ephys_preprocessing_process.name, "Ephys preprocessing")
        self.assertEqual(ephys_preprocessing_process.software_version, "0.1000.0")
        self.assertEqual(ephys_preprocessing_process.code_url, "my-code-repo")


class TestDataProcessUpgrade(unittest.TestCase):
    """Tests methods in DataProcessUpgrade class"""

    def test_upgrade_from_old_model(self):
        """Tests data process from old model is upgraded correctly."""
        start_date_time = datetime.datetime.fromisoformat("2023-02-22T18:16:35.919299+00:00")
        end_date_time = datetime.datetime.fromisoformat("2023-02-22T18:41:06.929027+00:00")

        old_data_process_dict = dict(
            name="Ephys preprocessing",
            version="0.1.5",
            code_url="my-code-repo",
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            input_location="my-input-location",
            output_location="my-output-location",
            parameters={"param1": "value1"},
        )
        upgrader = DataProcessUpgrade(old_data_process_dict=old_data_process_dict)
        new_data_process = upgrader.upgrade()

        # the upgrader updates version to software_version
        self.assertEqual(new_data_process.software_version, "0.1.5")
        self.assertEqual(new_data_process.code_url, "my-code-repo")
        self.assertEqual(new_data_process.start_date_time, start_date_time)
        self.assertEqual(new_data_process.end_date_time, end_date_time)
        self.assertEqual(new_data_process.input_location, "my-input-location")
        self.assertEqual(new_data_process.output_location, "my-output-location")
        self.assertEqual(new_data_process.parameters, AindGeneric.model_validate({"param1": "value1"}))

    def test_upgrade_from_other_with_no_notes(self):
        """Tests "Other" data process with not "notes" is upgraded correctly."""
        processing_path = PROCESSING_FILES_PATH / "processing_other_no_notes.json"
        with open(processing_path, "r") as f:
            processing_dict = json.load(f)
        data_process_no_notes_dict = processing_dict["data_processes"][1]

        upgrader = DataProcessUpgrade(data_process_no_notes_dict)
        new_data_process = upgrader.upgrade()

        # the upgrader updates version to software_version
        self.assertEqual(new_data_process.software_version, "0.29.3")
        self.assertEqual(
            new_data_process.code_url,
            "https://github.com/AllenNeuralDynamics/aind-data-transfer",
        )
        # notes that are None for "Other" data processes are replaced with "missing notes"
        self.assertEqual(new_data_process.notes, "missing notes")

    def test_upgrade_from_current_model(self):
        """Tests data process from current model is upgraded correctly."""
        datetime_now = datetime.datetime.now(datetime.timezone.utc)
        data_process_dict = dict(
            name="Ephys preprocessing",
            software_version="0.1.5",
            code_url="my-code-repo",
            start_date_time=datetime_now,
            end_date_time=datetime_now,
            input_location="my-input-location",
            output_location="my-output-location",
            parameters={"param1": "value1"},
        )

        upgrader = DataProcessUpgrade(old_data_process_dict=data_process_dict)
        new_data_process = upgrader.upgrade()

        # the upgrader updates version to software_version
        self.assertEqual(new_data_process.software_version, "0.1.5")
        self.assertEqual(new_data_process.code_url, "my-code-repo")
        self.assertEqual(new_data_process.start_date_time, datetime_now)
        self.assertEqual(new_data_process.end_date_time, datetime_now)
        self.assertEqual(new_data_process.input_location, "my-input-location")
        self.assertEqual(new_data_process.output_location, "my-output-location")
        self.assertEqual(new_data_process.parameters, AindGeneric(param1="value1"))


if __name__ == "__main__":
    unittest.main()
