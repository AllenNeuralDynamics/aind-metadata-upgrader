"""Main entrypoint to the metadata-upgrader"""

import unittest
import os
import json

from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient

API_GATEWAY_HOST = os.getenv("API_GATEWAY_HOST", "api.allenneuraldynamics-test.org")
DATABASE = os.getenv("DATABASE", "metadata_index")
COLLECTION = "assets"

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
                    print(f"Testing upgrade for {file_path}")
                    data = file.read()
                    # Here you would call the upgrade function
                    # For example: upgraded_data = upgrade(data)
                    # Then you can assert the expected outcome

                    upgraded = Upgrade(json.loads(data))
                    self.assertIsNotNone(upgraded)

                    client.upsert_one_docdb_record(
                        record=upgraded.metadata.model_dump(),
                    )



if __name__ == "__main__":
    unittest.main()
