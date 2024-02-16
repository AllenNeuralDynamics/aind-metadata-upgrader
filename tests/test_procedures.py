from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
)

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

from glob import glob
import json
from pathlib import Path

procedures_files = glob("tests/resources/procedures/class_model_examples/*.json")
print(procedures_files)

for file in procedures_files:
    with open(file) as f:
        subject = Path(file).stem
        print(file)
        print(subject)
        procedures = json.load(f)
        print("input procedure: ", procedures)
        ProcedureUpgrader = ProcedureUpgrade(procedures)

        test = ProcedureUpgrader.upgrade_procedure()

        test.write_standard_file(output_directory=Path("tests/resources/procedures/updated_class_models"), prefix=Path(subject))

    break
