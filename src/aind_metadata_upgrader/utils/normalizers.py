"""Pre-upgrade normalization utilities.

These functions normalize raw v1 metadata records before the upgraders run,
resolving name mismatches that would otherwise produce duplicate components
in the upgraded output.

All normalizations are conservative: they are applied **only** when there is
an unambiguous 1-to-1 mapping between the old and new names.  Rig / instrument
names are treated as the ground truth; canonical names are derived from the rig
camera assembly names and propagated into the session.
"""

import copy
import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_base_name(name: str) -> str:
    """Strip a trailing ' camera assembly' or ' camera' suffix (case-insensitive).

    The longer suffix is tried first so that names already in canonical form
    (e.g. ``'Face camera assembly'``) round-trip cleanly.

    Examples
    --------
    >>> _extract_base_name('Face Camera')
    'Face'
    >>> _extract_base_name('Face camera assembly')
    'Face'
    >>> _extract_base_name('Eye')  # no suffix
    'Eye'
    """
    name = re.sub(r"\s+camera\s+assembly\s*$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s+camera\s*$", "", name, flags=re.IGNORECASE).strip()
    return name


def _get_session_camera_names(session: dict) -> list:
    """Return the ordered, de-duplicated list of camera names from all
    ``data_streams`` entries in a v1 session record."""
    seen: set = set()
    names: list = []
    for stream in session.get("data_streams", []):
        for name in stream.get("camera_names", []):
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _get_rig_camera_assembly_names(rig: dict) -> list:
    """Return the ordered, de-duplicated list of top-level assembly names from
    a v1 rig record's ``cameras`` and ``camera_assemblies`` lists."""
    seen: set = set()
    names: list = []
    for section in ("cameras", "camera_assemblies"):
        for item in rig.get(section) or []:
            name = item.get("name", "")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _build_camera_normalization_plan(rig_names: list) -> dict | None:
    """Build a normalization plan driven by rig camera assembly names.

    For each rig assembly name the base is extracted by stripping a trailing
    ' camera' suffix.  The canonical names are then:

    * assembly: ``"{base} camera assembly"``
    * inner camera device: ``"{base} camera"``

    Returns ``None`` when any two rig assemblies share the same base (ambiguous).
    Returns an empty dict when the list is empty.

    Parameters
    ----------
    rig_names:
        Ordered list of rig camera assembly names.

    Returns
    -------
    dict mapping ``current_rig_assembly_name`` ->
        ``{"assembly_name": str, "camera_name": str, "base_lower": str}``
    """
    if not rig_names:
        return {}

    plan: dict = {}
    seen_bases: set = set()

    for rig_name in rig_names:
        base = _extract_base_name(rig_name)
        base_lower = base.lower()
        if base_lower in seen_bases:
            logger.debug(
                "Pre-upgrade normalisation: two rig camera assemblies share "
                "base '%s' – skipping camera normalisation.",
                base_lower,
            )
            return None
        seen_bases.add(base_lower)
        plan[rig_name] = {
            "assembly_name": f"{base} camera assembly",
            "camera_name": f"{base} camera",
            "base_lower": base_lower,
        }

    return plan


# ---------------------------------------------------------------------------
# Public normalisation functions
# ---------------------------------------------------------------------------


def normalize_camera_names(data: dict) -> dict:
    """Normalise camera assembly names using the rig as ground truth.

    Derives a canonical base name from each rig camera assembly by stripping
    its trailing ' camera' suffix (e.g. ``'Face Camera'`` → base ``'Face'``).
    The rig assembly and its inner camera device are then renamed to a
    consistent, unambiguous scheme:

    * assembly ``name``:        ``"{base} camera assembly"``  (e.g. ``'Face camera assembly'``)
    * inner ``camera.name``:   ``"{base} camera"``            (e.g. ``'Face camera'``)

    Having distinct assembly and device names eliminates the duplicate-name
    warnings produced by ``aind_data_schema``'s ``Instrument`` validator.

    Session ``camera_names`` that fuzzy-match a rig assembly (same base) are
    updated to the new assembly name so that the session and rig remain
    consistent (rig is ground truth, session is updated to match).

    The normalisation is skipped entirely if any two rig assemblies share the
    same base (ambiguous).

    Parameters
    ----------
    data:
        Raw record dict that may contain ``'session'`` and ``'rig'`` keys.

    Returns
    -------
    dict
        A deep copy of *data* with names updated, or the original *data*
        unchanged if no normalisation was required / possible.
    """
    rig = data.get("rig") or {}
    if not rig:
        return data

    rig_camera_names = _get_rig_camera_assembly_names(rig)
    plan = _build_camera_normalization_plan(rig_camera_names)

    if plan is None or not plan:
        return data

    # Determine whether anything actually needs changing before deep-copying.
    needs_change = False
    for section in ("cameras", "camera_assemblies"):
        for item in rig.get(section) or []:
            rig_name = item.get("name", "")
            if rig_name in plan:
                info = plan[rig_name]
                if item["name"] != info["assembly_name"]:
                    needs_change = True
                    break
                inner_name = (item.get("camera") or {}).get("name", "")
                if inner_name and inner_name != info["camera_name"]:
                    needs_change = True
                    break

    session = data.get("session") or {}
    base_lower_to_info = {info["base_lower"]: info for info in plan.values()}
    if not needs_change and session:
        for stream in session.get("data_streams", []):
            for cam_name in stream.get("camera_names", []):
                base = _extract_base_name(cam_name).lower()
                if base in base_lower_to_info:
                    if cam_name != base_lower_to_info[base]["assembly_name"]:
                        needs_change = True
                        break

    if not needs_change:
        return data

    data = copy.deepcopy(data)

    # Rename rig camera assemblies and their inner cameras.
    for section in ("cameras", "camera_assemblies"):
        for item in data["rig"].get(section, []):
            rig_name = item.get("name", "")
            if rig_name not in plan:
                continue
            info = plan[rig_name]
            if item["name"] != info["assembly_name"]:
                logger.info(
                    "Pre-upgrade normalisation: renaming rig %s '%s' → '%s'",
                    section.rstrip("s"),
                    rig_name,
                    info["assembly_name"],
                )
                item["name"] = info["assembly_name"]
            camera = item.get("camera")
            if camera and camera.get("name") != info["camera_name"]:
                logger.info(
                    "Pre-upgrade normalisation: renaming inner camera '%s' → '%s'",
                    camera["name"],
                    info["camera_name"],
                )
                camera["name"] = info["camera_name"]

    # Update session camera_names to use the new assembly names.
    if session:
        for stream in data["session"].get("data_streams", []):
            new_names = []
            for cam_name in stream.get("camera_names", []):
                base = _extract_base_name(cam_name).lower()
                if base in base_lower_to_info:
                    new_name = base_lower_to_info[base]["assembly_name"]
                    if cam_name != new_name:
                        logger.info(
                            "Pre-upgrade normalisation: renaming session "
                            "camera_name '%s' → '%s'",
                            cam_name,
                            new_name,
                        )
                    new_names.append(new_name)
                else:
                    new_names.append(cam_name)
            stream["camera_names"] = new_names

    return data


def pre_upgrade_normalize(data: dict) -> dict:
    """Apply all pre-upgrade normalisations to a raw metadata record.

    Currently normalises:
    * Camera assembly names (session ↔ rig).

    Each normalisation is conservative and is skipped when any ambiguity is
    detected, so the function is safe to call on all records.

    Parameters
    ----------
    data:
        Raw record dict (as loaded from the document-db or a JSON file).

    Returns
    -------
    dict
        The record with normalisations applied (deep-copied when changed).
    """
    data = normalize_camera_names(data)
    return data
