""" tests for Procedures upgrades """

import json
import logging
import os
import re
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

from aind_data_schema.core.procedures import CraniotomyType
from pydantic import __version__ as pyd_version

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

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

        logging.info("BEGIN ERROR TESTING")

        procedure_files: List[str] = os.listdir(PROCESSING_FILES_PATH)
        procedures = []

        for file in procedure_files:
            with open(PROCESSING_FILES_PATH / file, "r") as f:
                contents = json.load(f)
            procedures.append((file, contents))
        cls.procedures = dict(procedures)

        logging.info(f"test procedures: {cls.procedures}")

    def test_upgrade_procedure(self):
        """Test the upgrade_procedure method."""

        logging.info("Begin upgrading all procedures")

        for file, procedure in self.procedures.items():
            logging.info(f"LOADING PROCEDURE: {procedure}")
            ProcedureUpgrader = ProcedureUpgrade(procedure, allow_validation_errors=True)

            test = ProcedureUpgrader.upgrade_procedure()

            self.assertIsNotNone(test)

            logging.info("Procedure Saved")

    def test_craniotomy_upgrade(self):
        """Test the upgrade_craniotomy method."""

        logging.info("Begin testing craniotomy upgrades")

        test_file1 = self.procedures["676909.json"]

        upgrader = ProcedureUpgrade(test_file1, allow_validation_errors=False)

        p1 = upgrader.upgrade_procedure()

        self.assertEqual(p1.subject_procedures[1].procedures[0].craniotomy_type, CraniotomyType.WHC)

        test_file2 = self.procedures["667825.json"]

        upgrader = ProcedureUpgrade(test_file2, allow_validation_errors=False)

        p2 = upgrader.upgrade_procedure()

        self.assertEqual(p2.subject_procedures[0].procedures[0].craniotomy_type, CraniotomyType.VISCTX)

    def test_bad_type(self):
        """Test the upgrade_procedure method with a bad type."""

        logging.info("Begin testing bad type")

        test_file = self.procedures["609281_invalid_type.json"]

        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=False)

        with self.assertRaises(ValueError):
            upgrader.upgrade_procedure()

    def test_probe_upgrade(self):
        """Test the probe upgrading logic of ProceduresUpgrader"""

        logging.info("Begin testing probe upgrades")

        test_file = self.procedures["664644.json"]

        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=True)

        p = upgrader.upgrade_procedure()

        self.assertEqual(p.subject_procedures[1].procedures[2].probes[0].ophys_probe.core_diameter_unit, "um")
        self.assertEqual(p.subject_procedures[1].procedures[2].probes[1].ophys_probe.name, "Probe B")
        self.assertEqual(
            p.subject_procedures[1].procedures[2].probes[1].stereotactic_coordinate_ap,
            Decimal(-6.20000000000000017763568394002504646778106689453125),
        )

    def test_headframe_upgrade(self):
        """Test the headframe upgrading logic of ProceduresUpgrader"""

        logging.info("Begin testing headframe upgrades")

        test_file = self.procedures["652742.json"]

        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=True)

        p = upgrader.upgrade_procedure()

        self.assertEqual(p.subject_procedures[1].procedures[0].headframe_type, "AI Straight bar")

    def test_nanoject_upgrade(self):
        """Test the nanoject injection upgrading logic of ProceduresUpgrader"""

        logging.info("Begin testing nanoject upgrades")

        test_file = self.procedures["652504_U19.json"]

        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=True)

        p = upgrader.upgrade_procedure()

        self.assertEqual(
            p.subject_procedures[1].procedures[0].injection_materials[1].name, "AAV1-CAG-H2B-mTurquoise2-WPRE"
        )

    def test_perfusion_upgrade(self):
        """Test the perfusion upgrading logic of ProceduresUpgrader"""

        logging.info("Begin testing perfusion upgrades")

        test_file = self.procedures["653980.json"]

        upgrader = ProcedureUpgrade(test_file, allow_validation_errors=True)

        p = upgrader.upgrade_procedure()

        self.assertEqual(p.subject_procedures[1].procedures[0].output_specimen_ids, ["653980"])
