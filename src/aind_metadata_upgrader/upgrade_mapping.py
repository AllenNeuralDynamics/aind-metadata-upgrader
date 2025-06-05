"""Mapping or core file / version number combinations to their upgrade functions."""

from packaging.specifiers import SpecifierSet

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2
from aind_metadata_upgrader.instrument.v1v2 import InstrumentUpgraderV1V2
from aind_metadata_upgrader.quality_control.v1v2 import QCUpgraderV1V2
from aind_metadata_upgrader.rig.v1v2 import RigUpgraderV1V2
from aind_metadata_upgrader.subject.v1v2 import SubjectUpgraderV1V2
from aind_metadata_upgrader.processing.v1v2 import ProcessingV1V2

ACQUISITION = [
    (SpecifierSet("<=2.0.0"), None),
]

DATA_DESCRIPTION = [
    (SpecifierSet("<=2.0.0"), DataDescriptionV1V2),
]

INSTRUMENT = [
    (SpecifierSet("<=2.0.0"), InstrumentUpgraderV1V2),
]

METADATA = [
    (SpecifierSet("<=2.0.0"), None),
]

PROCEDURES = [
    (SpecifierSet("<=2.0.0"), None),
]

PROCESSING = [
    (SpecifierSet("<=2.0.0"), ProcessingV1V2),
]

QUALITY_CONTROL = [
    (SpecifierSet("<=2.0.0"), QCUpgraderV1V2),
]

RIG = [
    (SpecifierSet("<=2.0.0"), RigUpgraderV1V2),
]

SESSION = [
    (SpecifierSet("<=2.0.0"), None),
]

SUBJECT = [
    (SpecifierSet("<=2.0.0"), SubjectUpgraderV1V2),
]

MAPPING = {
    "acquisition": ACQUISITION,
    "data_description": DATA_DESCRIPTION,
    "instrument": INSTRUMENT,
    "metadata": METADATA,
    "procedures": PROCEDURES,
    "processing": PROCESSING,
    "quality_control": QUALITY_CONTROL,
    "rig": RIG,
    "session": SESSION,
    "subject": SUBJECT,
}
