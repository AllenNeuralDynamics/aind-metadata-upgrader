""" tests for Processing upgrades """

import re
import unittest
from pathlib import Path

from aind_data_schema.base import AindModel
from pydantic import __version__ as pyd_version

from aind_metadata_upgrader.utils import get_or_default

class TestUtils(unittest.TestCase):
    """Class for testing utilities."""

    def test_get_or_default(self):
        """Test the get_or_default function."""

        class TestModel(AindModel):
            """Model for testing utilities"""

            test: str
            test2: str = "default"

        test_case = {
            "test": "test",
        }

        self.assertEqual(get_or_default(test_case, TestModel, "test"), "test")
        self.assertEqual(get_or_default(test_case, TestModel, "test2"), "default")
        self.assertEqual(get_or_default(test_case, TestModel, "test3"), None)
