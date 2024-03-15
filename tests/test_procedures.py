""" tests for Procedures upgrades """

from datetime import datetime
import json
import os
import re
import unittest
import logging
from glob import glob
from pathlib import Path
from typing import List


from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade
from aind_data_schema.core.procedures import Procedures


from pydantic import __version__ as pyd_version

PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)

PROCESSING_FILES_PATH = Path(__file__).parent / "resources" / "procedures" / "class_model_examples"
PYD_VERSION = re.match(r"(\d+.\d+).\d+", pyd_version).group(1)

log_file_name = "./tests/resources/procedures/log_files/log_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler(log_file_name, "w", "utf-8")
fh.setLevel(logging.DEBUG)

# create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(fh)

class TestProceduresUpgrade(unittest.TestCase):
    """Test methods in ProceduresUpgrade class"""

    @classmethod
    def setUpClass(cls):
        """Load json files before running tests."""

        print("hi")

        logging.info("BEGIN ERROR TESTING")

        procedure_files: List[str] = os.listdir(PROCESSING_FILES_PATH)
        procedures = []

        for file in procedure_files:
            with open(PROCESSING_FILES_PATH / file, "r") as f:
                contents = json.load(f)
            procedures.append((file, Procedures.model_construct(**contents)))
        cls.procedures = dict(procedures)

        logging.info(f"test procedures: {cls.procedures}")