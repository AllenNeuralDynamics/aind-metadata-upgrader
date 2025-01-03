"""Test the v1->v2 upgrader"""

import json
import unittest
import os
from pathlib import Path
from aind_metadata_upgrader.upgrader import Upgrader

path = Path(os.path.dirname(os.path.abspath(__file__)))


class TestUpgrader(unittest.TestCase):
    """Class for testing upgrader."""

    def test_v1_v2(self):
        """Test the V1 to V2 upgrader"""

        with open(path / "resources/v1/5f6325ff-5920-429c-880b-35e287af716a.json") as f:
            data = json.load(f)

        data_v2 = Upgrader(data).upgrade()
        self.assertIsNotNone(data_v2)
