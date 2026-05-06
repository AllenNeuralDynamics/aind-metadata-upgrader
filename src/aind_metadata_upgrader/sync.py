"""Sync code to upgrade metadata from v1 to v2 and store results in ZS"""

import logging
import os
from typing import Optional
from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient
from zombie_squirrel import custom
import pandas as pd
from aind_metadata_upgrader import __version__ as upgrader_version


DOCDB_HOST = os.getenv("DOCDB_HOST", "api.allenneuraldynamics.org")
BATCH_SIZE = 100


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
_ZS_COLUMNS = ["v1_id", "v2_id", "upgrader_version", "last_modified", "upgrade_datetime", "status"]

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
    except ValueError as e:
        logging.info(f"No previous tracking data found, starting fresh: {e}")
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
    logging.info(f"Uploading {len(combined)} tracking records to ZS")
    custom(TABLE_NAME, df=combined)
    _zs_df = combined


def _get_cache_row(df: pd.DataFrame, record_id: str) -> dict:
    """Return the tracking row for a record from the ZS dataframe, or {}."""
    existing = df[df["v1_id"] == str(record_id)]
    return existing.iloc[0].to_dict() if len(existing) > 0 else {}


# ---------------------------------------------------------------------------
# Per-record decision / action helpers
# ---------------------------------------------------------------------------

def _should_skip(row: dict, data_dict: dict, v2_record: Optional[dict], upgrade_datetime: Optional[str]) -> bool:
    """Return True if this record should not be upgraded, logging the reason.

    Bypass — v2 exists and was externally modified (e.g. QC update) after the last upgrade.
    Skip   — record is already up-to-date with the current upgrader and v1 data.

    Note: if upgrade_datetime is set but v2 no longer exists, we do NOT bypass —
    the record should be re-upgraded to recreate the v2 document.
    """
    if not upgrade_datetime:
        return False
    record_id = data_dict.get("_id")
    if v2_record is None:
        # v2 was deleted externally — re-upgrade to recreate it
        return False
    if v2_record.get("_last_modified") != upgrade_datetime:
        logging.info(f"Record {record_id}: bypassing — v2 was externally modified after last upgrade")
        return True
    if (
        row.get("upgrader_version") == upgrader_version
        and row.get("last_modified") == data_dict.get("last_modified")
    ):
        logging.info(f"Record {record_id}: skipping — already up-to-date")
        return True
    return False


def _get_v2_record(location: str) -> Optional[dict]:
    """Fetch the current V2 record by location, or None if not found."""
    records = client_v2.retrieve_docdb_records(
        filter_query={"location": location},
        limit=1,
    )
    return records[0] if records else None


def _delete_v2_record(
    location: str,
    upgrade_datetime: Optional[str],
    v2_record: Optional[dict] = None,
) -> None:
    """Delete the V2 record for a location on upgrade failure, if safe to do so.

    Only deletes if upgrade_datetime is empty (record was never successfully tracked),
    or if upgrade_datetime matches the V2 record's current last_modified (meaning V2
    has not been externally modified since the last upgrade).

    Pass v2_record if already fetched to avoid a redundant network call.
    """
    if v2_record is None:
        v2_record = _get_v2_record(location)
    if not v2_record:
        return
    v2_last_modified = v2_record.get("_last_modified")
    if upgrade_datetime and v2_last_modified != upgrade_datetime:
        logging.info(
            f"Skipping delete: v2 record was externally modified after upgrading "
            f"(location={location})"
        )
        return
    logging.info(f"Deleting v2 record due to failed upgrade: {v2_record['_id']}")
    client_v2.delete_one_record(v2_record["_id"])


def upgrade_record(data_dict: dict, existing_v2_id: Optional[str] = None) -> Optional[dict]:
    """Run the upgrader on a v1 record.

    Returns the upgraded model dump (with _id set if updating an existing record),
    or None if the upgrade fails.
    """
    upgraded = Upgrade(data_dict)
    if not upgraded:
        return None
    model = upgraded.metadata.model_dump()
    if existing_v2_id is not None:
        model["_id"] = existing_v2_id
    return model


def _make_failure_result(data_dict: dict) -> dict:
    """Build a tracking dict representing a failed upgrade for a V1 record."""
    return {
        "v1_id": str(data_dict["_id"]),
        "v2_id": None,
        "upgrader_version": upgrader_version,
        "last_modified": data_dict.get("last_modified"),
        "upgrade_datetime": None,
        "status": "failed",
    }


def _attempt_upgrade(
    data_dict: dict,
    v2_record: Optional[dict],
    upgrade_datetime: Optional[str],
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
        upgraded_model = upgrade_record(data_dict, existing_v2_id)
    except Exception as e:
        logging.error(f"Upgrade failed for record {record_id}: {e}")

    if upgraded_model is None:
        if location:
            _delete_v2_record(location, upgrade_datetime, v2_record)
        return None, _make_failure_result(data_dict)

    return upgraded_model, None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def _flush_pending_upserts(
    pending_upserts: list[tuple[dict, str, str, dict]],
    upgrade_results: list[dict],
) -> None:
    """Batch upsert pending records to V2 and capture upgrade_datetime for each.

    After the batch upsert the V2 records are fetched back by _id so that
    the DB-assigned last_modified value can be stored as upgrade_datetime.

    Args:
        pending_upserts: List of (upgraded_model, location, record_id, data_dict) tuples.
        upgrade_results: List to append completed result dicts to.
    """
    if not pending_upserts:
        return
    records_to_upsert = [model for model, _, _, _ in pending_upserts]
    logging.info(f"Batch upserting {len(records_to_upsert)} records to DocumentDB")
    try:
        client_v2.upsert_list_of_docdb_records(records=records_to_upsert)
    except Exception as e:
        logging.warning(f"Batch upsert failed ({e}), falling back to individual upserts")
        for model, location, record_id, data_dict in pending_upserts:
            try:
                client_v2.upsert_one_docdb_record(record=model)
                v2_after = _get_v2_record(location)
                upgrade_results.append({
                    "v1_id": str(record_id),
                    "v2_id": str(model["_id"]),
                    "upgrader_version": upgrader_version,
                    "last_modified": data_dict.get("last_modified"),
                    "upgrade_datetime": v2_after.get("_last_modified") if v2_after else None,
                    "status": "success",
                })
            except Exception as e2:
                logging.error(f"Individual upsert failed for record {record_id}: {e2}")
                upgrade_results.append(_make_failure_result(data_dict))
        return

    # Fetch back by _id to capture the DB-assigned last_modified as upgrade_datetime
    ids = [model["_id"] for model, _, _, _ in pending_upserts]
    v2_records_after = client_v2.retrieve_docdb_records(
        filter_query={"_id": {"$in": ids}},
        projection={"_id": 1, "_last_modified": 1},
    )
    id_to_last_modified = {r["_id"]: r.get("_last_modified") for r in v2_records_after}

    for model, location, record_id, data_dict in pending_upserts:
        upgrade_results.append({
            "v1_id": str(record_id),
            "v2_id": str(model["_id"]),
            "upgrader_version": upgrader_version,
            "last_modified": data_dict.get("last_modified"),
            "upgrade_datetime": id_to_last_modified.get(model["_id"]),
            "status": "success",
        })


def run_one(record_id: str):
    """
    Upgrade a single V1 record and persist the result to the ZS tracking table.

    Decision logic is the same as run() — see _should_skip for details.
    """
    logging.info(f"Processing single record ID: {record_id}")

    records = client_v1.retrieve_docdb_records(filter_query={"_id": record_id})
    if not records:
        raise ValueError(f"Record ID {record_id} not found in v1 database")

    data_dict = records[0]
    location = data_dict.get("location")

    zs_df = _load_zs_cache()
    row = _get_cache_row(zs_df, record_id)
    upgrade_datetime = row.get("upgrade_datetime") or None

    # Fetch current V2 record once — reused for bypass/skip check and upsert
    v2_record = _get_v2_record(location) if location else None

    if _should_skip(row, data_dict, v2_record, upgrade_datetime):
        return

    existing_v2_id = v2_record["_id"] if v2_record else None

    upgraded_model, failure_result = _attempt_upgrade(data_dict, v2_record, upgrade_datetime)
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

    v2_record_after = _get_v2_record(location)
    result = {
        "v1_id": str(record_id),
        "v2_id": str(existing_v2_id),
        "upgrader_version": upgrader_version,
        "last_modified": data_dict.get("last_modified"),
        "upgrade_datetime": v2_record_after.get("_last_modified") if v2_record_after else None,
        "status": "success",
    }
    logging.info(f"Successfully processed record {record_id}")
    _save_results(zs_df, [result])


def run():
    """Upgrade all V1 records and persist results to the ZS tracking table.

    Per-record decision logic is identical to run_one(). Existing records are
    queued and batch-upserted for efficiency; new records are inserted
    individually so the DB-assigned _id can be captured immediately.
    """
    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1})
    record_ids = [record["_id"] for record in records_list]
    logging.info(f"Found {len(record_ids)} records to process")

    num_records = len(records_list)
    zs_df = _load_zs_cache()

    # Prune tracking rows whose v1_id no longer exists in the v1 database
    if len(record_ids) > 0:
        record_ids_set = {str(rid) for rid in record_ids}
        zs_df = zs_df[zs_df["v1_id"].isin(record_ids_set)]
        logging.info(f"Filtered tracking data to {len(zs_df)} records that exist in v1 database")

    upgrade_results: list[dict] = []
    # List of (upgraded_model, location, record_id, data_dict) awaiting batch upsert
    pending_upserts: list[tuple[dict, str, str, dict]] = []

    for i in range(0, num_records, BATCH_SIZE):
        logging.info(f"Records: {i}/{num_records}")
        batch_ids = record_ids[i: i + BATCH_SIZE]
        cached_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": batch_ids}},
        )

        for data_dict in cached_records:
            record_id = data_dict["_id"]
            location = data_dict.get("location")
            logging.info(f"Testing upgrade for record ID: {record_id}")

            row = _get_cache_row(zs_df, record_id)
            upgrade_datetime = row.get("upgrade_datetime") or None

            # Fetch current V2 record once — reused for bypass/skip check and upsert
            v2_record = _get_v2_record(location) if location else None

            if _should_skip(row, data_dict, v2_record, upgrade_datetime):
                continue

            existing_v2_id = v2_record["_id"] if v2_record else None

            upgraded_model, failure_result = _attempt_upgrade(data_dict, v2_record, upgrade_datetime)
            if failure_result is not None:
                upgrade_results.append(failure_result)
                continue

            if existing_v2_id:
                # Existing record — queue for batch upsert
                pending_upserts.append((upgraded_model, location, record_id, data_dict))
            else:
                # New record — insert immediately so we can capture the assigned _id
                try:
                    response = client_v2.insert_one_docdb_record(record=upgraded_model)
                except Exception as e:
                    logging.error(f"Failed to insert record {record_id} to V2: {e}")
                    upgrade_results.append(_make_failure_result(data_dict))
                    continue
                new_v2_id = response.json().get("insertedId", "")
                v2_after = _get_v2_record(location)
                upgrade_results.append({
                    "v1_id": str(record_id),
                    "v2_id": str(new_v2_id),
                    "upgrader_version": upgrader_version,
                    "last_modified": data_dict.get("last_modified"),
                    "upgrade_datetime": v2_after.get("_last_modified") if v2_after else None,
                    "status": "success",
                })

        # Flush batch when it has grown to BATCH_SIZE
        if len(pending_upserts) >= BATCH_SIZE:
            _flush_pending_upserts(pending_upserts, upgrade_results)
            pending_upserts.clear()

    # Final flush of any remaining pending upserts
    if pending_upserts:
        _flush_pending_upserts(pending_upserts, upgrade_results)

    _save_results(zs_df, upgrade_results)
