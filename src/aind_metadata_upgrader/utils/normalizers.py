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


def _rig_needs_camera_rename(rig: dict, plan: dict) -> bool:
    """Return True if any rig camera assembly or its inner camera needs renaming."""
    for section in ("cameras", "camera_assemblies"):
        for item in rig.get(section) or []:
            rig_name = item.get("name", "")
            if rig_name not in plan:
                continue
            info = plan[rig_name]
            if item["name"] != info["assembly_name"]:
                return True
            inner_name = (item.get("camera") or {}).get("name", "")
            if inner_name and inner_name != info["camera_name"]:
                return True
    return False


def _session_needs_camera_rename(session: dict, base_lower_to_info: dict) -> bool:
    """Return True if any session camera_name differs from the canonical assembly name."""
    for stream in session.get("data_streams", []):
        for cam_name in stream.get("camera_names", []):
            base = _extract_base_name(cam_name).lower()
            if base in base_lower_to_info and cam_name != base_lower_to_info[base]["assembly_name"]:
                return True
    return False


def _apply_rig_camera_renames(rig: dict, plan: dict) -> None:
    """Rename camera assemblies and inner cameras in-place according to *plan*."""
    for section in ("cameras", "camera_assemblies"):
        for item in rig.get(section, []):
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


def _apply_session_camera_renames(session: dict, base_lower_to_info: dict) -> None:
    """Rewrite session camera_names in-place to canonical assembly names."""
    for stream in session.get("data_streams", []):
        new_names = []
        for cam_name in stream.get("camera_names", []):
            base = _extract_base_name(cam_name).lower()
            if base in base_lower_to_info:
                new_name = base_lower_to_info[base]["assembly_name"]
                if cam_name != new_name:
                    logger.info(
                        "Pre-upgrade normalisation: renaming session camera_name '%s' → '%s'",
                        cam_name,
                        new_name,
                    )
                new_names.append(new_name)
            else:
                new_names.append(cam_name)
        stream["camera_names"] = new_names


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

    plan = _build_camera_normalization_plan(_get_rig_camera_assembly_names(rig))
    if not plan:
        return data

    session = data.get("session") or {}
    base_lower_to_info = {info["base_lower"]: info for info in plan.values()}

    needs_change = _rig_needs_camera_rename(rig, plan) or _session_needs_camera_rename(session, base_lower_to_info)
    if not needs_change:
        return data

    data = copy.deepcopy(data)
    _apply_rig_camera_renames(data["rig"], plan)
    if session:
        _apply_session_camera_renames(data["session"], base_lower_to_info)

    return data


_FIBER_UNDERSCORE_RE = re.compile(r"^Fiber_(\d+)$")


def _has_fiber_underscore_name(obj) -> bool:
    """Return True if any 'name' field anywhere in *obj* contains a Fiber_N value."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "name" and isinstance(v, str) and _FIBER_UNDERSCORE_RE.match(v):
                return True
            if _has_fiber_underscore_name(v):
                return True
    elif isinstance(obj, list):
        return any(_has_fiber_underscore_name(item) for item in obj)
    return False


def _fix_fiber_names(obj):
    """Return a new object with Fiber_N replaced by Fiber N in every 'name' field."""
    if isinstance(obj, dict):
        return {
            k: re.sub(r"^Fiber_(\d+)$", r"Fiber \1", v)
            if k == "name" and isinstance(v, str)
            else _fix_fiber_names(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_fix_fiber_names(item) for item in obj]
    return obj


def normalize_fiber_names(data: dict) -> dict:
    """Normalize fiber name fields: replace ``'Fiber_N'`` with ``'Fiber N'`` in any
    ``'name'`` field found anywhere in the record.

    The substitution is driven by the regex ``^Fiber_(\\d+)$``, so only exact
    matches are changed (e.g. ``"Fiber_0"`` → ``"Fiber 0"``).  Fields named
    anything other than ``"name"`` are left untouched.

    Parameters
    ----------
    data:
        Raw record dict.

    Returns
    -------
    dict
        A deep copy with all matching name fields normalised, or the original
        *data* dict unchanged when no normalisation is needed.
    """
    if not _has_fiber_underscore_name(data):
        return data
    return _fix_fiber_names(copy.deepcopy(data))


def pre_upgrade_normalize(data: dict) -> dict:
    """Apply all pre-upgrade normalisations to a raw metadata record.

    Currently normalises:
    * Camera assembly names (session ↔ rig).
    * Fiber name fields: ``'Fiber_N'`` → ``'Fiber N'`` in any ``'name'`` field.

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
    data = normalize_fiber_names(data)
    return data
