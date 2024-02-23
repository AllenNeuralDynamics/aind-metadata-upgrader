from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
)

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

from glob import glob
import json
from pathlib import Path
import logging

import logging
from datetime import datetime
# You can set the ouput location to whatever. You may need to create a 'logs' folder in the scratch
# directory beforehand.

log_file_name = "./tests/resources/procedures/log_files/log_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler(log_file_name)
fh.setLevel(logging.DEBUG)


# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(fh)


procedures_files = glob("tests/resources/procedures/class_model_examples/*.json")
print(procedures_files)

import json


def replace_placeholders(json_para: str, search_para, replace_para):
    # Local nested function.
    def decode_dict(a_dict):
        if search_para in a_dict.values():
            for key, value in a_dict.items():
                if value == search_para:
                    a_dict[key] = replace_para
        return a_dict
    return json.loads(json_para, object_hook=decode_dict)

for file in procedures_files:
    if "652742" not in file:
        continue 

    with open(file, "r", encoding="UTF-8") as f:
        contents = json.loads(f.read().encode('UTF-8').decode())

    result = replace_placeholders(json.dumps(contents), 'μm', 'um')
    logging.info("replaced file: ", result)

    with open(file) as f:
        subject = Path(file).stem
        procedures = json.load(f)
        logging.info("PROCEDURES: ", type(procedures))
        ProcedureUpgrader = ProcedureUpgrade(procedures)

        test = ProcedureUpgrader.upgrade_procedure()

        test.write_standard_file(output_directory=Path("tests/resources/procedures/updated_class_models"), prefix=Path(subject))

