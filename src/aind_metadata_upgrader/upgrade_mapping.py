"""Mapping or core file / version number combinations to their upgrade functions."""

from packaging.specifiers import SpecifierSet

from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2
from aind_metadata_upgrader.subject.v1v2 import SubjectUpgraderV1V2

ACQUISITION = [
    (SpecifierSet("<=1.0.4"), None),
]

DATA_DESCRIPTION = [
    (SpecifierSet("<=1.0.4"), DataDescriptionV1V2),
]

INSTRUMENT = [
    (SpecifierSet("<=1.0.4"), None),
]

METADATA = [
    (SpecifierSet("<=1.2.1"), None),
]

PROCEDURES = [
    (SpecifierSet("<=1.2.1"), None),
]

PROCESSING = [
    (SpecifierSet("<=1.1.4"), None),
]

QUALITY_CONTROL = [
    (SpecifierSet("<=1.2.2"), None),
]

RIG = [
    (SpecifierSet("<=1.1.1"), None),
]

SESSION = [
    (SpecifierSet("<=1.1.2"), None),
]

SUBJECT = [
    (SpecifierSet("<=1.0.3"), SubjectUpgraderV1V2),
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
