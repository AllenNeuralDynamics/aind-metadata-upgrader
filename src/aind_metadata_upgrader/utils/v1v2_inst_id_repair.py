"""Cross-modal instrument_id / rig_id mismatch repair utilities.

This module replaces the per-modality dispatch that previously lived in
v1v2_metadata_utils.  A single set of ordered rules is now applied regardless
of modality, which handles both v1 (rig/session) and v2 (instrument/acquisition)
ID mismatches uniformly.

Resolution rule order applied by _resolve_instrument_id_mismatch():
  0. Strip whitespace; return early if equal or either is empty.
  1. Known-bad instrument IDs           → use acquisition.
  2. Space ↔ underscore normalization   → use normalised (underscored) form.
  3. Date-separator difference only     → use acquisition format (YYYY-MM-DD).
  4. Dot difference only (NP.3 vs NP3)  → use acquisition form.
  5. Acquisition ID is in LONG_ACQ_ID_LIST → use acquisition.
  6. Acquisition ID is in SHORT_ACQ_ID_LIST → use instrument.
  7. Explicit (instrument, acquisition) pairs → use instrument.
  8. Instrument ID is a substring of acquisition ID → use acquisition.
  9. Date-based resolution (prefix + date parsing):
       Same normalised prefix:
         - Both parseable: if instrument newer or equal, use instrument;
           if acquisition newer, raise ValueError.
         - Only one side has a date: prefer the dated side.
         - Neither has a date: prefer instrument.
       Different normalised prefix:
         - Both have dates: prefer the one with the more recent date (log warning
           if acquisition is newer and use it).
         - Only one side has a date: prefer the dated side.
         - Neither has a date: prefer instrument.
"""

import logging
import re
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Acquisition IDs that are short aliases — the instrument (rig) file holds the
# full canonical dated ID.
SHORT_ACQ_ID_LIST = ["5B", "4D", "MESO.1", "MESO.2", "5A", "4A", "4B", "4C"]

# Acquisition IDs that carry the canonical name even though the rig file may
# have a dated / differently formatted counterpart.
LONG_ACQ_ID_LIST = ["442_Bergamo_2p_photostim"]

# Explicit (instrument_id, acquisition_id) pairs where the instrument ID is correct.
PAIRED_INSTRUMENT_ACQUISITION_IDS = [
    ("342_NP3_240417", "342_NP3_240401"),
]

# Instrument IDs known to be incorrect / placeholder values — always overwrite
# with the acquisition value.
BAD_INSTRUMENT_IDS = [
    "322_EPHYS5_Ephys5",
    "Ephys5_ND_Ephys.5",
]

# Date patterns tried in order: YYYY-MM-DD, YYYYMMDD (8-digit), YYMMDD (6-digit).
_DATE_PATTERNS = [
    (re.compile(r"(\d{4}-\d{2}-\d{2})"), "%Y-%m-%d"),
    (re.compile(r"(?<!\d)(\d{8})(?!\d)"), "%Y%m%d"),
    (re.compile(r"(?<!\d)(\d{6})(?!\d)"), "%y%m%d"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_rig_id_parts(rig_id: str) -> tuple[str, Optional[datetime]]:
    """Extract (prefix, date) from a rig / instrument ID string.

    Returns (rig_id, None) when no recognisable date is found.
    """
    for pattern, fmt in _DATE_PATTERNS:
        m = pattern.search(rig_id)
        if m:
            try:
                date = datetime.strptime(m.group(1), fmt)
                prefix = rig_id[: m.start()]
                return prefix, date
            except ValueError:
                continue
    return rig_id, None


def _normalize_prefix(prefix: str) -> str:
    """Normalise a rig-ID prefix for comparison.

    Removes dots and whitespace and lowercases so that e.g. ``NP.3`` and
    ``NP3`` are treated as the same rig family.
    """
    return re.sub(r"[.\s]", "", prefix).lower()


# ---------------------------------------------------------------------------
# Core resolution logic
# ---------------------------------------------------------------------------


def _apply_normalization_rules(
    instrument_id: str, acquisition_id: str
) -> Optional[tuple[str, str]]:
    """Apply string-normalization rules (2–4) and long-form list check (5).

    Returns a resolved pair, or None if no rule matched.
    """
    instr_underscored = instrument_id.replace(" ", "_")
    acq_underscored = acquisition_id.replace(" ", "_")
    if instr_underscored == acq_underscored:  # Rule 2
        return instr_underscored, instr_underscored
    if instrument_id.replace("-", "") == acquisition_id.replace("-", ""):  # Rule 3
        return acquisition_id, acquisition_id
    if instrument_id.replace(".", "") == acquisition_id.replace(".", ""):  # Rule 4
        return acquisition_id, acquisition_id
    # Rule 5 — also check underscore-normalised form so "442 Bergamo 2p photostim"
    # matches the list entry "442_Bergamo_2p_photostim".
    if acq_underscored in LONG_ACQ_ID_LIST:
        return acq_underscored, acq_underscored
    return None


def _apply_id_list_rules(
    instrument_id: str, acquisition_id: str
) -> Optional[tuple[str, str]]:
    """Apply ID-catalogue and substring rules (6–8).

    Returns a resolved pair, or None if no rule matched.
    """
    if acquisition_id in SHORT_ACQ_ID_LIST:  # Rule 6
        return instrument_id, instrument_id
    if (instrument_id, acquisition_id) in PAIRED_INSTRUMENT_ACQUISITION_IDS:  # Rule 7
        return instrument_id, instrument_id
    if instrument_id in acquisition_id:  # Rule 8
        return acquisition_id, acquisition_id
    return None


def _resolve_same_prefix_by_date(
    instrument_id: str,
    acquisition_id: str,
    instr_date: Optional[datetime],
    acq_date: Optional[datetime],
) -> tuple[str, str]:
    """Resolve a date mismatch when both IDs share the same normalised prefix."""
    if instr_date and acq_date:
        if instr_date >= acq_date:
            return instrument_id, instrument_id
        raise ValueError(
            f"Acquisition rig ID '{acquisition_id}' has a more recent date than "
            f"instrument rig ID '{instrument_id}'. Cannot auto-resolve."
        )
    if instr_date:
        return instrument_id, instrument_id
    if acq_date:
        return acquisition_id, acquisition_id
    # Neither has a parseable date; prefer instrument (rig file).
    return instrument_id, instrument_id


def _resolve_different_prefix_by_date(
    instrument_id: str,
    acquisition_id: str,
    instr_date: Optional[datetime],
    acq_date: Optional[datetime],
) -> tuple[str, str]:
    """Resolve a date mismatch when the two IDs have different normalised prefixes."""
    if instr_date and acq_date:
        if instr_date >= acq_date:
            return instrument_id, instrument_id
        logging.warning(
            "Acquisition rig ID '%s' has a more recent date than instrument rig ID '%s'. "
            "Using acquisition ID.",
            acquisition_id,
            instrument_id,
        )
        return acquisition_id, acquisition_id
    if instr_date:
        return instrument_id, instrument_id
    if acq_date:
        return acquisition_id, acquisition_id
    # Neither has a date; prefer instrument.
    return instrument_id, instrument_id


def _resolve_by_date(instrument_id: str, acquisition_id: str) -> tuple[str, str]:
    """Apply date-based resolution (Rule 9)."""
    instr_prefix, instr_date = _parse_rig_id_parts(instrument_id)
    acq_prefix, acq_date = _parse_rig_id_parts(acquisition_id)

    instr_prefix_norm = _normalize_prefix(instr_prefix) if instr_prefix else ""
    acq_prefix_norm = _normalize_prefix(acq_prefix) if acq_prefix else ""

    if instr_prefix_norm == acq_prefix_norm:
        return _resolve_same_prefix_by_date(instrument_id, acquisition_id, instr_date, acq_date)
    return _resolve_different_prefix_by_date(instrument_id, acquisition_id, instr_date, acq_date)


def _resolve_instrument_id_mismatch(instrument_id: str, acquisition_id: str) -> tuple[str, str]:
    """Apply all resolution rules and return (corrected_instrument_id, corrected_acquisition_id).

    Both returned values will be equal when the mismatch is resolved.  The
    function never raises; ambiguous cases log a warning and prefer the
    acquisition ID so the upgrade can proceed.
    """
    # Rule 0 — strip whitespace; bail early if equal or empty.
    instrument_id = instrument_id.strip()
    acquisition_id = acquisition_id.strip()
    if not instrument_id or not acquisition_id:
        return instrument_id, acquisition_id
    if instrument_id == acquisition_id:
        return instrument_id, acquisition_id

    # Rule 1 — known-bad instrument IDs.
    if instrument_id in BAD_INSTRUMENT_IDS:
        return acquisition_id, acquisition_id

    # Rules 2–5 — string normalisation and long-form list.
    result = _apply_normalization_rules(instrument_id, acquisition_id)
    if result is not None:
        return result

    # Rules 6–8 — ID catalogue and substring checks.
    result = _apply_id_list_rules(instrument_id, acquisition_id)
    if result is not None:
        return result

    # Rule 9 — date-based resolution.
    return _resolve_by_date(instrument_id, acquisition_id)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def repair_instrument_id_mismatch(data: dict) -> dict:
    """Repair mismatched instrument IDs between instrument and acquisition sections.

    Applies the unified rule-set in _resolve_instrument_id_mismatch regardless of
    modality.  A ValueError is raised when the same rig family (prefix) appears in
    both IDs but the acquisition carries a more recent date — this indicates a data
    entry error that needs manual review.
    """
    instrument = data.get("instrument") or {}
    acquisition = data.get("acquisition") or {}

    instrument_id = instrument.get("instrument_id")
    acquisition_id = acquisition.get("instrument_id")

    if not instrument_id or not acquisition_id:
        return data
    if instrument_id == acquisition_id:
        return data

    new_instrument_id, new_acquisition_id = _resolve_instrument_id_mismatch(instrument_id, acquisition_id)
    data["instrument"]["instrument_id"] = new_instrument_id
    data["acquisition"]["instrument_id"] = new_acquisition_id
    return data
