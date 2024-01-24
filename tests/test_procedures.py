from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
)

from aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

from glob import glob
import json

procedures_files = glob("tests/resources/procedures/*.json")

with open(procedures_files[0]) as f:
    procedures = json.load(f)
    ProcedureUpgrader = ProcedureUpgrade(dict(procedures))

    test = ProcedureUpgrader.upgrade_procedure()

    print(test)
