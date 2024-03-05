""" tests for Processing upgrades """

import datetime
import json
import os
import re
import unittest
from pathlib import Path
from typing import List

from pydantic import __version__ as pyd_version

from aind_metadata_upgrader.utils import *


PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)

PROCESSING_FILES_PATH = Path(__file__).parent / "resources" / "ephys_processing"
PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)


class TestUtils(unittest.TestCase):
    
    def test_get_or_default():
        pass