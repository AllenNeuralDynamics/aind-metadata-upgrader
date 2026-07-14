"""Sync code to upgrade metadata from v1 to v2 and store results in ZS"""

import contextlib
import io
import logging
import os
from typing import Optional
from packaging.version import Version
from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient
from biodata_cache import custom
import pandas as pd
from aind_metadata_upgrader import __version__ as upgrader_version

_logger = logging.getLogger(__name__)

# Loggers that emit noisy WARNING-level messages during model construction/validation
_NOISY_LOGGERS = [
    "aind_data_schema",
    "aind_metadata_upgrader.upgrade",
    "aind_metadata_upgrader.procedures",
    "aind_metadata_upgrader.instrument",
    "aind_metadata_upgrader.acquisition",
    "aind_metadata_upgrader.data_description",
    "aind_metadata_upgrader.session",
    "aind_metadata_upgrader.subject",
    "aind_metadata_upgrader.rig",
    "aind_metadata_upgrader.processing",
    "aind_metadata_upgrader.quality_control",
]


@contextlib.contextmanager
def _quiet_upgrade():
    """Suppress stdout and noisy WARNING-level log messages during upgrade."""
    saved = {name: logging.getLogger(name).level for name in _NOISY_LOGGERS}
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        for name, level in saved.items():
            logging.getLogger(name).setLevel(level)


DOCDB_HOST = os.getenv("DOCDB_HOST", "api.allenneuraldynamics.org")
BATCH_SIZE = 50


# docdb
client_v1 = MetadataDbClient(
    host=DOCDB_HOST,
    version="v1",
)

client_v2 = MetadataDbClient(
    host=DOCDB_HOST,
    version="v2",
)


# cache settings
# we'll store v1_id, v2_id, upgrade_version, status
TABLE_NAME = os.getenv("TABLE_NAME", "metadata_upgrade_status_prod")
_ZS_COLUMNS = ["v1_id", "v2_id", "upgrader_version", "last_modified", "status"]

# In-memory cache of the ZS table for the current process lifetime
_zs_df: Optional[pd.DataFrame] = None


# ---------------------------------------------------------------------------
# ZS cache helpers
# ---------------------------------------------------------------------------


def _load_zs_cache() -> pd.DataFrame:
    """Load (or return the already-cached) ZS tracking table."""
    global _zs_df
    if _zs_df is not None:
        return _zs_df
    try:
        candidate = custom(TABLE_NAME)
        if "v1_id" not in candidate.columns or len(candidate) == 0:
            raise ValueError("Table empty or missing v1_id column")
        _zs_df = candidate
        versions = candidate["upgrader_version"].unique().tolist() if "upgrader_version" in candidate.columns else []
        print(f"Loaded tracking table: {len(candidate)} records (versions in cache: {versions})")
        print(f"Current upgrader_version: {upgrader_version}")
    except ValueError as e:
        print(f"No previous tracking data found, starting fresh: {e}")
        _zs_df = pd.DataFrame(columns=_ZS_COLUMNS)
    return _zs_df


def _save_results(base_df: pd.DataFrame, results: list[dict]) -> None:
    """Merge upgrade results into the ZS tracking table and upload.

    Writes back even when results is empty so that a pruned base_df (with
    stale rows removed) is always persisted.
    """
    global _zs_df
    new_rows = pd.DataFrame(results) if results else pd.DataFrame(columns=_ZS_COLUMNS)
    combined = pd.concat([base_df, new_rows], ignore_index=True)
    combined = combined.drop_duplicates(subset=["v1_id"], keep="last")
    print(f"Uploading {len(combined)} tracking records to ZS")
    custom(TABLE_NAME, df=combined)
    _zs_df = combined


def _get_cache_row(df: pd.DataFrame, record_id: str) -> dict:
    """Return the tracking row for a record from the ZS dataframe, or {}."""
    existing = df[df["v1_id"] == str(record_id)]
    return existing.iloc[0].to_dict() if len(existing) > 0 else {}


# ---------------------------------------------------------------------------
# Per-record decision / action helpers
# ---------------------------------------------------------------------------


def _get_v2_record(location: str) -> Optional[dict]:
    """Fetch the current V2 record by location, or None if not found."""
    records = client_v2.retrieve_docdb_records(
        filter_query={"location": location},
        limit=1,
    )
    return records[0] if records else None


def _delete_v2_record(location: str, v2_record: Optional[dict] = None) -> None:
    """Delete the V2 record for a location on upgrade failure."""
    if v2_record is None:
        v2_record = _get_v2_record(location)
    if not v2_record:
        return
    print(f"Deleting v2 record due to failed upgrade: {v2_record['_id']}")
    client_v2.delete_one_record(v2_record["_id"])


def upgrade_record(data_dict: dict, existing_v2_id: Optional[str] = None) -> Optional[dict]:
    """Run the upgrader on a v1 record.

    Returns the upgraded model dump (with _id set if updating an existing record),
    or None if the upgrade fails.  When updating an existing record the
    quality_control field is stripped so that any edits made directly to V2
    are preserved.
    """
    upgraded = Upgrade(data_dict)
    if not upgraded:
        return None
    model = upgraded.metadata.model_dump()
    if existing_v2_id is not None:
        model["_id"] = existing_v2_id
        model.pop("quality_control", None)
    return model


def _make_failure_result(data_dict: dict) -> dict:
    """Build a tracking dict representing a failed upgrade for a V1 record."""
    return {
        "v1_id": str(data_dict["_id"]),
        "v2_id": None,
        "upgrader_version": upgrader_version,
        "last_modified": data_dict.get("last_modified"),
        "status": "failed",
    }


def _attempt_upgrade(
    data_dict: dict,
    v2_record: Optional[dict],
) -> tuple[Optional[dict], Optional[dict]]:
    """Try to upgrade a V1 record, cleaning up V2 on failure.

    Returns (upgraded_model, None) on success, or (None, failure_result) on failure,
    where failure_result is a tracking dict ready to be passed to _save_results.
    """
    record_id = data_dict["_id"]
    location = data_dict.get("location")
    existing_v2_id = v2_record["_id"] if v2_record else None

    upgraded_model = None
    try:
        with _quiet_upgrade():
            upgraded_model = upgrade_record(data_dict, existing_v2_id)
    except Exception as e:
        logging.error(f"Upgrade failed for record {record_id}: {e}")

    if upgraded_model is None:
        if location:
            _delete_v2_record(location, v2_record)
        return None, _make_failure_result(data_dict)

    return upgraded_model, None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _process_record(
    data_dict: dict,
    zs_df: pd.DataFrame,
    upgrade_results: list[dict],
    pending_upserts: list[tuple],
    v2_record: Optional[dict] = None,
) -> str:
    """Evaluate and process a single V1 record within a run() batch.

    Returns a status string indicating what happened:
      "failed"        — upgrade or insert failed
      "inserted"      — new v2 record successfully created
      "queued_upsert" — existing v2 record queued for batch upsert
    """
    record_id = data_dict["_id"]
    location = data_dict.get("location")

    row = _get_cache_row(zs_df, record_id)
    if row.get("upgrader_version") == upgrader_version and row.get("last_modified") == data_dict.get("last_modified"):
        _logger.debug(f"Record {record_id}: skipping — already up-to-date")
        return "skipped"

    # v2_record is pre-fetched by the batch; fall back to individual fetch if not supplied
    if v2_record is None and location:
        v2_record = _get_v2_record(location)

    existing_v2_id = v2_record["_id"] if v2_record else None

    upgraded_model, failure_result = _attempt_upgrade(data_dict, v2_record)
    if failure_result is not None:
        upgrade_results.append(failure_result)
        return "failed"

    if existing_v2_id:
        # Existing record — queue for batch upsert
        pending_upserts.append((upgraded_model, location, record_id, data_dict))
        return "queued_upsert"
    else:
        # New record — insert immediately so we can capture the assigned _id
        try:
            response = client_v2.insert_one_docdb_record(record=upgraded_model)
        except Exception as e:
            logging.error(f"Failed to insert record {record_id} to V2: {e}")
            upgrade_results.append(_make_failure_result(data_dict))
            return "failed"
        new_v2_id = response.json().get("insertedId", "")
        upgrade_results.append(
            {
                "v1_id": str(record_id),
                "v2_id": str(new_v2_id),
                "upgrader_version": upgrader_version,
                "last_modified": data_dict.get("last_modified"),
                "status": "success",
            }
        )
        return "inserted"


def _build_upgrade_set(record_ids: list, zs_df: pd.DataFrame) -> list:
    """Pre-pass: batch-fetch slim projections to identify records that need upgrading.

    Fetches only _id and last_modified in batches of BATCH_SIZE, checks each
    record against the ZS cache skip condition, and returns an ordered list of
    IDs that must be upgraded (i.e. not already up-to-date).
    """
    needs_upgrade: list = []
    for i in range(0, len(record_ids), BATCH_SIZE):
        batch_ids = record_ids[i: i + BATCH_SIZE]
        slim_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": batch_ids}},
            projection={"_id": 1, "last_modified": 1},
        )
        for rec in slim_records:
            row = _get_cache_row(zs_df, rec["_id"])
            if not (
                row.get("upgrader_version") == upgrader_version and row.get("last_modified") == rec.get("last_modified")
            ):
                needs_upgrade.append(rec["_id"])
    print(f"Pre-pass complete: {len(needs_upgrade)}/{len(record_ids)} records need upgrading")
    return needs_upgrade


def _flush_pending_upserts(
    pending_upserts: list[tuple[dict, str, str, dict]],
    upgrade_results: list[dict],
) -> None:
    """Upsert pending records to V2 individually.

    Args:
        pending_upserts: List of (upgraded_model, location, record_id, data_dict) tuples.
        upgrade_results: List to append completed result dicts to.
    """
    if not pending_upserts:
        return

    print(f"Upserting {len(pending_upserts)} records to DocumentDB individually")

    for model, location, record_id, data_dict in pending_upserts:
        try:
            client_v2.upsert_one_docdb_record(record=model)
            upgrade_results.append(
                {
                    "v1_id": str(record_id),
                    "v2_id": str(model["_id"]),
                    "upgrader_version": upgrader_version,
                    "last_modified": data_dict.get("last_modified"),
                    "status": "success",
                }
            )
        except Exception as e:
            logging.error(f"Individual upsert failed for record {record_id}: {e}")
            upgrade_results.append(_make_failure_result(data_dict))


def run_one(record_id: str):
    """
    Upgrade a single V1 record and persist the result to the ZS tracking table.

    Decision logic is the same as run() — see _should_skip for details.
    """
    print(f"Processing single record ID: {record_id}")

    records = client_v1.retrieve_docdb_records(filter_query={"_id": record_id})
    if not records:
        raise ValueError(f"Record ID {record_id} not found in v1 database")

    data_dict = records[0]
    location = data_dict.get("location")

    zs_df = _load_zs_cache()

    # Refuse to downgrade: if the cache already records a newer upgrader version, abort
    row = _get_cache_row(zs_df, record_id)
    cached_version = row.get("upgrader_version")
    if cached_version and Version(cached_version) > Version(upgrader_version):
        print(
            f"Skipping record {record_id}: cached upgrader version {cached_version} "
            f"is newer than current {upgrader_version}"
        )
        return

    # Fetch current V2 record to determine if this is an insert or upsert
    v2_record = _get_v2_record(location) if location else None
    existing_v2_id = v2_record["_id"] if v2_record else None

    upgraded_model, failure_result = _attempt_upgrade(data_dict, v2_record)
    if failure_result is not None:
        logging.warning(f"Upgrade failed for record {record_id}")
        _save_results(zs_df, [failure_result])
        return

    if existing_v2_id:
        try:
            client_v2.upsert_one_docdb_record(record=upgraded_model)
        except Exception as e:
            logging.error(f"Failed to upsert record {record_id} to V2: {e}")
            _save_results(zs_df, [_make_failure_result(data_dict)])
            return
    else:
        try:
            response = client_v2.insert_one_docdb_record(record=upgraded_model)
        except Exception as e:
            logging.error(f"Failed to insert record {record_id} to V2: {e}")
            _save_results(zs_df, [_make_failure_result(data_dict)])
            return
        existing_v2_id = response.json().get("insertedId", "")

    result = {
        "v1_id": str(record_id),
        "v2_id": str(existing_v2_id),
        "upgrader_version": upgrader_version,
        "last_modified": data_dict.get("last_modified"),
        "status": "success",
    }
    print(f"Successfully processed record {record_id}")
    _save_results(zs_df, [result])


def run():
    """Upgrade all V1 records and persist results to the ZS tracking table."""
    global _zs_df
    _zs_df = None

    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1})
    record_ids = [record["_id"] for record in records_list]
    num_records = len(record_ids)
    print(f"Found {num_records} records to process")

    zs_df = _load_zs_cache()

    # Prune tracking rows whose v1_id no longer exists in the v1 database
    if num_records > 0:
        record_ids_set = {str(rid) for rid in record_ids}
        zs_df = zs_df[zs_df["v1_id"].isin(record_ids_set)]
        print(f"Filtered tracking data to {len(zs_df)} records that exist in v1 database")

    # Pre-pass: identify which records actually need upgrading without fetching full payloads
    ids_to_upgrade = _build_upgrade_set(record_ids, zs_df)
    num_to_upgrade = len(ids_to_upgrade)
    num_skipped = num_records - num_to_upgrade
    print(f"Skipping {num_skipped} already up-to-date records; upgrading {num_to_upgrade}")

    all_upgrade_results: list[dict] = []
    all_pending_upserts: list[tuple] = []
    summary_stats: dict[str, int] = {
        "inserted": 0,
        "queued_upsert": 0,
        "failed": 0,
        "skipped": num_skipped,
    }
    upgraded_names: list[str] = []
    failed_names: list[str] = []

    for i in range(0, num_to_upgrade, BATCH_SIZE):
        batch_ids = ids_to_upgrade[i: i + BATCH_SIZE]
        batch_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": batch_ids}},
        )
        id_to_record = {r["_id"]: r for r in batch_records}
        for record_id in batch_ids:
            data_dict = id_to_record.get(record_id)
            if not data_dict:
                logging.warning(f"Record {record_id} not found in v1 database, skipping")
                continue
            status = _process_record(data_dict, zs_df, all_upgrade_results, all_pending_upserts)
            summary_stats[status] = summary_stats.get(status, 0) + 1
            name = data_dict.get("location") or str(record_id)
            if status in ("inserted", "queued_upsert"):
                upgraded_names.append(name)
            elif status == "failed":
                failed_names.append(name)
        print(f"Progress: {min(i + BATCH_SIZE, num_to_upgrade)}/{num_to_upgrade} upgrade-eligible records")
        _flush_pending_upserts(all_pending_upserts, all_upgrade_results)
        all_pending_upserts.clear()
        _save_results(zs_df, all_upgrade_results)
        all_upgrade_results.clear()
        zs_df = _zs_df  # pick up the updated dataframe for skip checks

    # If there were no batches at all (num_to_upgrade == 0), still persist the pruned zs_df
    if num_to_upgrade == 0:
        _save_results(zs_df, [])

    total_new = summary_stats["inserted"]
    total_re_upgraded = summary_stats["queued_upsert"]
    total_failed = summary_stats["failed"]
    total_skipped = summary_stats["skipped"]
    total_processed = total_new + total_re_upgraded + total_failed + total_skipped

    print("=" * 60)
    print("Upgrade run complete — summary:")
    print(f"  Total records in v1:          {num_records}")
    print(f"  Total processed:              {total_processed}")
    print(f"  New upgrades (inserted):      {total_new}")
    print(f"  Re-upgraded (upserted):       {total_re_upgraded}")
    print(f"  Skipped (already up-to-date): {total_skipped}")
    print(f"  Failed:                       {total_failed}")
    print("=" * 60)
    if upgraded_names:
        print("\nUpgraded records:")
        for name in upgraded_names:
            print(f"  + {name}")
    if failed_names:
        print("\nFailed records:")
        for name in failed_names:
            print(f"  ! {name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    run()
