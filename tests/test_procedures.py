from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
)

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

from glob import glob
import json

procedures_files = glob("tests/resources/procedures/class_model_examples/*.json")

with open(procedures_files[0]) as f:
    print(procedures_files[0])
    procedures = json.load(f)
    print("input procedure: ", procedures)
    ProcedureUpgrader = ProcedureUpgrade(procedures)

    test = ProcedureUpgrader.upgrade_procedure()

    print(test)