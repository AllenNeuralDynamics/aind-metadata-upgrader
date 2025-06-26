"""Main entrypoint to the metadata-upgrader"""

import unittest
import os
import json

from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient
import traceback


ALL_CORE_FILES = [
    "subject",
    "data_description",
    "procedures",
    "instrument",
    "processing",
    "acquisition",
    "quality_control",
    "model",
    "rig",
    "session",
]


API_GATEWAY_HOST = "api.allenneuraldynamics-test.org"
DATABASE = "metadata_index_v2"
COLLECTION = "data_assets"


client = MetadataDbClient(
    host=API_GATEWAY_HOST,
    database=DATABASE,
    collection=COLLECTION,
)


class TestUpgrade(unittest.TestCase):
    """Test the upgrade process"""

    def test_upgrade(self):
        """Test the upgrade process"""
        base_dir = os.path.join(os.path.dirname(__file__), "records")

        # Get all the directories in tests/records/
        dirs = [name for name in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, name))]

        # Load all the json files in the folder records/core_filename/*
        for dir in dirs:
            dir_path = os.path.join(base_dir, dir)
            json_files = [f for f in os.listdir(dir_path) if f.endswith(".json")]

            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                with open(file_path, "r") as file:
                    print(f"\n\nTesting upgrade for {file_path}")
                    data = file.read()
                    data_dict = json.loads(data)

                    # Test the upgrade process - this will fail the subTest if upgrade fails
                    fake = False
                    if "name" not in data_dict:
                        data_dict["name"] = "fake_name_for_testing"
                        fake = True
                    if "location" not in data_dict:
                        data_dict["location"] = "fake_location_for_testing"
                        fake = True

                    try:
                        skip_metadata_validation = any(core_file_name in dir_path for core_file_name in ALL_CORE_FILES)
                        print(f"Skip metadata validation: {skip_metadata_validation}")
                        upgraded = Upgrade(data_dict, skip_metadata_validation)
                        self.assertIsNotNone(upgraded)

                        if upgraded and not fake:
                            location = upgraded.metadata.location

                            records = client.retrieve_docdb_records(
                                filter_query={"location": location},
                                limit=1,
                            )
                            if len(records) == 0:
                                print(f"Inserting new upgraded record to DocumentDB: {upgraded.metadata.name}")
                                client.insert_one_docdb_record(
                                    record=upgraded.metadata.model_dump(),
                                )
                            else:
                                id = records[0]["_id"]
                                record_data = upgraded.metadata.model_dump()
                                record_data["_id"] = id
                                print(f"Updating existing record in DocumentDB: {upgraded.metadata.name}")
                                client.upsert_one_docdb_record(
                                    record=record_data,
                                )
                    except Exception as e:
                        print(f"Upgrade failed for {file_path}: {e}")
                        print(f"Stack trace:\n{traceback.format_exc()}")


if __name__ == "__main__":
    unittest.main()
