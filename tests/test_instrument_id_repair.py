"""Tests for v1v2_inst_id_repair — coverage driven by the real-world mismatch CSV.

The CSV at tests/resources/instrument_id_mismatches.csv contains every unique
combination of rig_id / instrument_id mismatches observed across the v1 asset
database.  For each row we construct a minimal data dict and assert that
repair_instrument_id_mismatch produces matching IDs.

Column semantics
----------------
rig_rig_id              rig.rig_id from v1 schema (→ instrument.instrument_id after upgrade)
session_rig_id          session.rig_id from v1 schema (→ acquisition.instrument_id after upgrade)
instrument_instrument_id already-upgraded instrument.instrument_id
acquisition_instrument_id already-upgraded acquisition.instrument_id

For each row we use the populated pair.  If both pairs are populated we test
both.  Rows where either side is empty (after stripping) are skipped.
"""

import csv
import os
import unittest

from aind_metadata_upgrader.utils.v1v2_inst_id_repair import repair_instrument_id_mismatch

_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
_CSV_PATH = os.path.join(_RESOURCES_DIR, "instrument_id_mismatches.csv")


def _make_data(instrument_id: str, acquisition_id: str, modalities: str = "") -> dict:
    """Build a minimal data dict suitable for repair_instrument_id_mismatch."""
    modality_list = (
        [{"abbreviation": m} for m in modalities.split("|") if m]
        if modalities
        else []
    )
    return {
        "instrument": {"instrument_id": instrument_id},
        "acquisition": {"instrument_id": acquisition_id},
        "data_description": {"modality": modality_list},
    }


def _load_mismatch_pairs() -> list[tuple[str, str, str, str]]:
    """Return (instrument_id, acquisition_id, label, modalities) for every testable row."""
    pairs = []
    with open(_CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            modalities = row.get("modalities", "")

            # v1 schema pair: rig → instrument, session → acquisition
            rig = (row.get("rig_rig_id") or "").strip()
            session = (row.get("session_rig_id") or "").strip()
            if rig and session:
                pairs.append((rig, session, f"rig/session: {rig} | {session}", modalities))

            # Already-upgraded v2 pair
            instr = (row.get("instrument_instrument_id") or "").strip()
            acq = (row.get("acquisition_instrument_id") or "").strip()
            if instr and acq:
                pairs.append((instr, acq, f"instrument/acquisition: {instr} | {acq}", modalities))

    return pairs


class TestRepairInstrumentIdMismatch(unittest.TestCase):
    """Parametric tests: every mismatch row from the CSV must be resolved."""

    def _assert_resolved(self, instrument_id: str, acquisition_id: str, modalities: str):
        data = _make_data(instrument_id, acquisition_id, modalities)
        result = repair_instrument_id_mismatch(data)
        result_instr = result["instrument"]["instrument_id"]
        result_acq = result["acquisition"]["instrument_id"]
        self.assertEqual(
            result_instr,
            result_acq,
            f"IDs still differ after repair: instrument='{result_instr}' "
            f"acquisition='{result_acq}' "
            f"(original instrument='{instrument_id}', acquisition='{acquisition_id}')",
        )

    def test_all_csv_mismatches_are_resolved(self):
        """Every row in instrument_id_mismatches.csv must either produce matching IDs
        or raise a ValueError (same-prefix acquisition-newer case is an intentional
        hard failure that requires manual review)."""
        pairs = _load_mismatch_pairs()
        self.assertGreater(len(pairs), 0, "No mismatch rows loaded from CSV")

        failures = []
        for instrument_id, acquisition_id, label, modalities in pairs:
            try:
                self._assert_resolved(instrument_id, acquisition_id, modalities)
            except ValueError:
                pass  # expected for same-prefix acquisition-newer cases
            except AssertionError as exc:
                failures.append(f"  [{label}] {exc}")

        if failures:
            self.fail("The following rows were not resolved:\n" + "\n".join(failures))

    # ------------------------------------------------------------------
    # Deterministic unit tests for each rule (independent of CSV)
    # ------------------------------------------------------------------

    def test_already_equal_returns_unchanged(self):
        """Already-matching IDs should be left unchanged."""
        data = _make_data("342_NP3_240401", "342_NP3_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_240401")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240401")

    def test_missing_instrument_id_returns_unchanged(self):
        """Missing instrument_id — return data unchanged"""
        data = _make_data("", "342_NP3_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240401")

    def test_missing_acquisition_id_returns_unchanged(self):
        """Missing acquisition instrument_id — return data unchanged"""
        data = _make_data("342_NP3_240401", "")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_240401")

    # Rule 1 — known-bad instrument IDs
    def test_bad_instrument_id_overwritten_by_acquisition(self):
        """Known-bad instrument IDs are overwritten by the acquisition value"""
        data = _make_data("322_EPHYS5_Ephys5", "ND_Ephys.5")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "ND_Ephys.5")
        self.assertEqual(result["acquisition"]["instrument_id"], "ND_Ephys.5")

    def test_bad_instrument_id_ephys5_nd(self):
        """Ephys5_ND_Ephys.5 is a known bad ID that should be repaired to ND_Ephys.5"""
        data = _make_data("Ephys5_ND_Ephys.5", "ND_Ephys.5")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "ND_Ephys.5")

    # Rule 2 — space / underscore normalization
    def test_space_vs_underscore_normalized(self):
        """Space vs underscore — normalized to underscores, acquisition preferred"""
        data = _make_data("442 Bergamo 2p photostim", "442_Bergamo_2p_photostim")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "442_Bergamo_2p_photostim")
        self.assertEqual(result["acquisition"]["instrument_id"], "442_Bergamo_2p_photostim")

    def test_whitespace_only_acquisition_skipped(self):
        """Acquisition ID is only whitespace — skip repair, keep original instrument ID"""
        data = _make_data("426_4B_20250130", "  ")
        result = repair_instrument_id_mismatch(data)
        # Whitespace-only acquisition → no repair, original instrument preserved
        self.assertEqual(result["instrument"]["instrument_id"], "426_4B_20250130")

    # Rule 3 — date-separator normalization
    def test_yyyymmdd_vs_yyyy_mm_dd_uses_acquisition(self):
        """Date separator normalization — prefer acquisition format"""
        data = _make_data("323_EPHYS2_RF_20241222_01", "323_EPHYS2_RF_2024-12-22_01")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")
        self.assertEqual(result["acquisition"]["instrument_id"], "323_EPHYS2_RF_2024-12-22_01")

    def test_vr_rig_date_separator(self):
        """VR rig has YYYYMMDD vs session YYYY-MM-DD — prefer acquisition format"""
        data = _make_data("322_EPHYS5_VR_20251028_01", "322_EPHYS5_VR_2025-10-28_01")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "322_EPHYS5_VR_2025-10-28_01")

    # Rule 4 — dot normalization
    def test_dot_normalization_np3(self):
        """NP.3 vs NP3 with equal date — dot normalisation uses acquisition form (Rule 4)"""
        data = _make_data("342_NP.3_20241111", "342_NP3_20241111")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_20241111")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_20241111")

    # Rule 5 — LONG_ACQ_ID_LIST
    def test_long_acq_id_list_bergamo(self):
        """Long-form Bergamo photostim ID with date and room number, resolved via Rule 5"""
        data = _make_data("Bergamo_2p-photostim-room442_20241021", "442_Bergamo_2p_photostim")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "442_Bergamo_2p_photostim")
        self.assertEqual(result["acquisition"]["instrument_id"], "442_Bergamo_2p_photostim")

    def test_long_acq_id_list_bergamo_spaced(self):
        """Space version of the long-form Bergamo photostim ID, resolved via Rule 5"""
        # Space version of the long-form name, resolved via Rule 5 after underscore norm
        data = _make_data("Bergamo_2p-photostim-room442_20241021", "442 Bergamo 2p photostim")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "442_Bergamo_2p_photostim")

    # Rule 6 — SHORT_ACQ_ID_LIST
    def test_short_acq_id_meso1_uses_instrument(self):
        """Short acquisition ID 'MESO.1' vs instrument ID '429_MESO1_20260122' — prefer instrument"""
        data = _make_data("429_MESO1_20260122", "MESO.1")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "429_MESO1_20260122")
        self.assertEqual(result["acquisition"]["instrument_id"], "429_MESO1_20260122")

    def test_short_acq_id_5a_uses_instrument(self):
        """Short acquisition ID '5A' vs bad instrument ID '426_5A_20241126' — prefer acquisition"""
        data = _make_data("426_5A_20241126", "5A")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "426_5A_20241126")

    def test_short_acq_id_both_in_list_uses_instrument(self):
        """Short acquisition ID '4A' vs short instrument ID '4C' — both in SHORT_ACQ_ID_LIST; prefer instrument"""
        data = _make_data("4C", "4A")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "4C")
        self.assertEqual(result["acquisition"]["instrument_id"], "4C")

    # Rule 7 — explicit paired overrides
    def test_paired_instrument_acquisition(self):
        """Explicit paired override for instrument ID '342_NP3_240417' vs acquisition ID '342_NP3_240401' — prefer instrument"""
        data = _make_data("342_NP3_240417", "342_NP3_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_240417")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240417")

    # Rule 8 — instrument is a substring of acquisition
    def test_instrument_substring_of_acquisition(self):
        """Instrument ID is a substring of acquisition ID — prefer acquisition"""
        data = _make_data("station1", "my_station1_v2")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "my_station1_v2")
        self.assertEqual(result["acquisition"]["instrument_id"], "my_station1_v2")

    # Rule 9 — date-based, same prefix
    def test_same_prefix_instrument_newer_date(self):
        """Same prefix, instrument has newer date — copy instrument ID into acquisition"""
        data = _make_data("327_NP2_240418", "327_NP2_240401")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "327_NP2_240418")
        self.assertEqual(result["acquisition"]["instrument_id"], "327_NP2_240418")

    def test_same_prefix_instrument_older_date_raises(self):
        """Same prefix, session has newer date — raise ValueError for manual review"""
        # rig from Nov 2025, session from Dec 2025 → session newer → ValueError
        data = _make_data("155_Chronic1_20251107", "155_Chronic1_20251201")
        with self.assertRaises(ValueError) as ctx:
            repair_instrument_id_mismatch(data)
        self.assertIn("more recent date", str(ctx.exception))

    def test_same_prefix_instrument_very_old_date_raises(self):
        """Same prefix, session has much newer date — raise ValueError for manual review"""
        # rig from Feb 2023, session from Apr 2024 → session newer → ValueError
        data = _make_data("342_NP3_230207", "342_NP3_240401")
        with self.assertRaises(ValueError):
            repair_instrument_id_mismatch(data)

    def test_same_prefix_dated_instrument_undated_acquisition(self):
        """Same prefix, instrument has date but acquisition doesn't — prefer instrument"""
        data = _make_data("440_SmartSPIM1_20240710", "SmartSPIM1-7")
        result = repair_instrument_id_mismatch(data)
        # instrument has date → prefer instrument
        self.assertEqual(result["instrument"]["instrument_id"], "440_SmartSPIM1_20240710")
        self.assertEqual(result["acquisition"]["instrument_id"], "440_SmartSPIM1_20240710")

    def test_same_prefix_undated_instrument_dated_acquisition(self):
        """Same prefix, acquisition has date but instrument doesn't — prefer acquisition"""
        data = _make_data("SmartSPIM1-7", "440_SmartSPIM1_20240710")
        result = repair_instrument_id_mismatch(data)
        # acquisition has date → prefer acquisition
        self.assertEqual(result["instrument"]["instrument_id"], "440_SmartSPIM1_20240710")
        self.assertEqual(result["acquisition"]["instrument_id"], "440_SmartSPIM1_20240710")

    # Rule 9 — date-based, different prefix
    def test_different_prefix_prefer_instrument(self):
        """Different prefix (342_ vs unknown_) but instrument has more recent date — prefer instrument"""
        data = _make_data("342_NP3_240906", "unknown_NP3_240401")
        result = repair_instrument_id_mismatch(data)
        # rig (2024-09-06) > session (2024-04-01) and different prefix → instrument wins
        self.assertEqual(result["instrument"]["instrument_id"], "342_NP3_240906")
        self.assertEqual(result["acquisition"]["instrument_id"], "342_NP3_240906")

    def test_different_prefix_no_date_prefer_instrument(self):
        """Different prefix (428_ vs 428_) but no parseable date — prefer instrument"""
        data = _make_data("428_FIP1_1", "428_1_FIP1")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "428_FIP1_1")
        self.assertEqual(result["acquisition"]["instrument_id"], "428_FIP1_1")

    def test_different_prefix_undated_spim_ids(self):
        """Different prefix, no parseable date — prefer instrument (Rule 9 fallback)"""
        # SmartSPIM IDs with no parseable dates; instrument wins
        data = _make_data("SmartSPIM1-2", "SmartSPIM-2-1")
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "SmartSPIM1-2")
        self.assertEqual(result["acquisition"]["instrument_id"], "SmartSPIM1-2")

    def test_no_instrument_section(self):
        """No instrument section — return data unchanged"""
        data = {"acquisition": {"instrument_id": "some_id"}}
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["acquisition"]["instrument_id"], "some_id")

    def test_no_acquisition_section(self):
        """No acquisition section — return data unchanged"""
        data = {"instrument": {"instrument_id": "some_id"}}
        result = repair_instrument_id_mismatch(data)
        self.assertEqual(result["instrument"]["instrument_id"], "some_id")


if __name__ == "__main__":
    unittest.main()
