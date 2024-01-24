from aind_data_schema.core.procedures import (
    Procedures, 
    Surgery,
)

from src.aind_metadata_upgrader.procedures_upgrade import ProcedureUpgrade

from glob import glob

procedures_files = glob("data/procedures/*.json")

ProcedureUpgrader = ProcedureUpgrade()

test = ProcedureUpgrader.upgrade_procedure(procedures_files[0].json())
