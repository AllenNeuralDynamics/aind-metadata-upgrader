import json
import logging
from datetime import datetime
from glob import glob
from pathlib import Path

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

# You can set the ouput location to whatever. You may need to create a 'logs' folder in the scratch
# directory beforehand.

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


procedures_files = glob("tests/resources/procedures/class_model_examples/*.json")
print(procedures_files)


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
