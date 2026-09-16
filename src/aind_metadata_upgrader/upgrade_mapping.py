"""Mapping or core file / version number combinations to their upgrade functions."""

from packaging.specifiers import SpecifierSet

from aind_metadata_upgrader.acquisition.v1v2 import AcquisitionV1V2
from aind_metadata_upgrader.acquisition.v2v2 import AcquisitionUpgraderV2V2
from aind_metadata_upgrader.acquisition.v2v3 import AcquisitionUpgraderV2V3
from aind_metadata_upgrader.data_description.v1v2 import DataDescriptionV1V2
from aind_metadata_upgrader.instrument.v1v2 import InstrumentUpgraderV1V2
from aind_metadata_upgrader.instrument.v2v2 import InstrumentUpgraderV2V2
from aind_metadata_upgrader.instrument.v2v3 import InstrumentUpgraderV2V3
from aind_metadata_upgrader.metadata.v1v2 import MetadataUpgraderV1V2
from aind_metadata_upgrader.metadata.v2v3 import MetadataUpgraderV2V3
from aind_metadata_upgrader.procedures.v1v2 import ProceduresUpgraderV1V2
from aind_metadata_upgrader.procedures.v2v3 import ProceduresUpgraderV2V3
from aind_metadata_upgrader.processing.v1v2 import ProcessingV1V2
from aind_metadata_upgrader.quality_control.v1v2 import QCUpgraderV1V2
from aind_metadata_upgrader.quality_control.v2v3 import QCUpgraderV2V3
from aind_metadata_upgrader.rig.v1v2 import RigUpgraderV1V2
from aind_metadata_upgrader.session.v1v2 import SessionV1V2
from aind_metadata_upgrader.subject.v1v2 import SubjectUpgraderV1V2
from aind_metadata_upgrader.subject.v2v3 import SubjectUpgraderV2V3

ACQUISITION = [
    (SpecifierSet("<2.0.0"), AcquisitionV1V2),
    (SpecifierSet(">=2.0.0,<3.0.0"), AcquisitionUpgraderV2V2),
    (SpecifierSet("<3.0.0"), AcquisitionUpgraderV2V3),
]

DATA_DESCRIPTION = [
    (SpecifierSet("<2.0.0"), DataDescriptionV1V2),
]

INSTRUMENT = [
    (SpecifierSet("<2.0.0"), InstrumentUpgraderV1V2),
    (SpecifierSet(">=2.0.0,<3.0.0"), InstrumentUpgraderV2V2),
    (SpecifierSet("<3.0.0"), InstrumentUpgraderV2V3),
]

METADATA = [
    (SpecifierSet("<2.0.0"), MetadataUpgraderV1V2),
    (SpecifierSet("<3.0.0"), MetadataUpgraderV2V3),
]

PROCEDURES = [
    (SpecifierSet("<2.0.0"), ProceduresUpgraderV1V2),
    (SpecifierSet("<3.0.0"), ProceduresUpgraderV2V3),
]

PROCESSING = [
    (SpecifierSet("<2.0.0"), ProcessingV1V2),
]

QUALITY_CONTROL = [
    (SpecifierSet("<2.0.0"), QCUpgraderV1V2),
    (SpecifierSet("<3.0.0"), QCUpgraderV2V3),
]

RIG = [
    (SpecifierSet("<2.0.0"), RigUpgraderV1V2),
    (SpecifierSet("<3.0.0"), InstrumentUpgraderV2V3),
]

SESSION = [
    (SpecifierSet("<2.0.0"), SessionV1V2),
    (SpecifierSet("<3.0.0"), AcquisitionUpgraderV2V3),
]

SUBJECT = [
    (SpecifierSet("<2.0.0"), SubjectUpgraderV1V2),
    (SpecifierSet("<3.0.0"), SubjectUpgraderV2V3),
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
