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

    def test_upgrade_procedure(self):
        """Test the upgrade_procedure method."""

        for file, procedure in self.procedures.items():
            logging.info(f"PROCEDURE: {procedure}")
            ProcedureUpgrader = ProcedureUpgrade(procedure, allow_validation_errors=True)

            test = ProcedureUpgrader.upgrade_procedure()

            test.write_standard_file(
                output_directory=Path("tests/resources/procedures/updated_class_models"), prefix=Path(file)
            )
    
    def test_craniotomy_upgrade(self):
        """Test the upgrade_craniotomy method."""
        
        test_file = self.procedures["676909.json"]

        
        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=False)

        with self.assertRaises(Exception) as e:
            test = upgrader.upgrade_procedure()


for file in procedures_files:

    with open(file, "r") as f:
        contents = json.loads(f.read())

    # for procedure in contents["subject_procedures"]:
    #     logging.info(procedure)
    #     if "probes" in procedure.keys():
    #         if "um" in procedure["probes"]["core_diameter_unit"].replace("μm", "um"):
    #             logging.info("UPDATING CORE DIAMETER UNIT")
    #             procedure["probes"].pop("core_diameter_unit")
    #             procedure["probes"]["core_diameter_unit"] = "um"
    #             logging.info(procedure["probes"])

    with open(file) as f:
        subject = Path(file).stem
        procedures = json.load(f)
        logging.info(f"PROCEDURES: {type(procedures)}")
        ProcedureUpgrader = ProcedureUpgrade(procedures, allow_validation_errors=True)

        test = ProcedureUpgrader.upgrade_procedure()

        test.write_standard_file(
            output_directory=Path("tests/resources/procedures/updated_class_models"), prefix=Path(subject)
        )