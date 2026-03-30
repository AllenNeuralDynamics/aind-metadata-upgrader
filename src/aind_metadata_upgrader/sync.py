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


def _delete_v2_record(data_dict: dict) -> None:
    """Delete the v2 record for a failed upgrade, if one exists."""
    location = data_dict.get("location")
    if location:
        records = client_v2.retrieve_docdb_records(
            filter_query={"location": location},
            projection={"_id": 1},
            limit=1,
        )
        if records:
            v2_id = records[0]["_id"]
            logging.info(f"Deleting v2 record due to failed upgrade: {v2_id}")
            client_v2.delete_one_record(v2_id)


def upgrade_record(data_dict: dict) -> tuple[Optional[dict], dict]:
    """Upgrade a single record"""
    upgraded = Upgrade(data_dict)

    if upgraded:

        location = upgraded.metadata.location

        records = client_v2.retrieve_docdb_records(
            filter_query={"location": location},
            limit=1,
        )
        if len(records) == 0:
            logging.info(f"Inserting new upgraded record to DocumentDB: {upgraded.metadata.name}")
            response = client_v2.insert_one_docdb_record(
                record=upgraded.metadata.model_dump(),
            )
            v2_id = response.json().get("insertedId", "")
            new_record = None  # already inserted
        else:
            v2_id = records[0]["_id"]
            new_record = upgraded.metadata.model_dump()
            new_record["_id"] = v2_id
            logging.info(f"Batch updating existing record in DocumentDB: {upgraded.metadata.name}")

        return (
            new_record,
            {
                "v1_id": str(data_dict["_id"]),
                "v2_id": str(v2_id),
                "upgrader_version": upgrader_version,
                "last_modified": data_dict.get("last_modified"),
                "status": "success",
            },
        )
    else:
        _delete_v2_record(data_dict)
        return (
            None,
            {
                "v1_id": str(data_dict["_id"]),
                "v2_id": None,
                "upgrader_version": upgrader_version,
                "last_modified": data_dict.get("last_modified"),
                "status": "failed",
            },
        )


def get_zs_data() -> Optional[pd.DataFrame]:
    """Retrieve existing upgrade status data from cache"""
    try:
        df = custom(TABLE_NAME)
    except ValueError as e:
        logging.info(f"(METADATA VALIDATOR): No previous validation results found, starting fresh: {e}")
        df = None

    if df is not None and ("v1_id" not in df.columns or len(df) < 1):
        logging.info("(METADATA VALIDATOR): No previous validation results found, starting fresh")
        df = None

    return df


def upload_to_forest_helper(df: pd.DataFrame):
    """Upload upgrade results to cache"""
    logging.info(f"(METADATA VALIDATOR) Uploading {len(df)} records to cache")
    custom(TABLE_NAME, df=df)


def check_skip_conditions(data_dict: dict, original_df: Optional[pd.DataFrame]) -> bool:
    """Check if a record should be skipped based on existing ZS data"""
    v1_id = data_dict["_id"]
    if original_df is not None:
        existing = original_df[original_df["v1_id"] == str(v1_id)]
        if len(existing) > 0:
            row = existing.iloc[0]

            existing_upgrader_version = row.get("upgrader_version", "")
            existing_last_modified = row.get("last_modified", "")

            if existing_upgrader_version == upgrader_version and existing_last_modified == data_dict.get(
                "last_modified"
            ):
                logging.info(f"Skipping already successfully upgraded record ID {v1_id}")
                return True
    return False


def upload_to_forest(original_df: Optional[pd.DataFrame], upgrade_results: list[dict]):
    """Upload upgrade results to ZS"""
    # Upload any remaining tracking data
    if upgrade_results:
        logging.info(f"Uploading final batch of {len(upgrade_results)} tracking records to ZS")
        batch_df = pd.DataFrame(upgrade_results)
        try:
            if original_df is not None:
                # Merge with existing data
                combined_df = pd.concat([original_df, batch_df], ignore_index=True)
                # Remove duplicates, keeping the latest entry for each v1_id
                combined_df = combined_df.drop_duplicates(subset=["v1_id"], keep="last")
                upload_to_forest_helper(combined_df)
            else:
                upload_to_forest_helper(batch_df)
        except Exception as e:
            logging.warning(f"Failed to upload final tracking data to ZS: {e}")
    else:
        logging.info("(METADATA VALIDATOR) No upgrade results to write to ZS")


def query_zs_record(record_id: str) -> Optional[list]:
    """Query cache for a specific record by v1_id.

    Args:
        record_id: The v1 record ID to query

    Returns:
        List of matching rows (typically 0 or 1 row), or None if query fails
    """
    try:
        df = custom(TABLE_NAME)
        matching = df[df["v1_id"] == str(record_id)]
        return matching.to_dict("records") if len(matching) > 0 else []
    except Exception as e:
        logging.warning(f"Error querying cache for record {record_id}: {e}")
        return None


def should_skip_record(existing_row: Optional[list], data_dict: dict) -> bool:
    """Check if a record should be skipped based on existing ZS data.

    Args:
        existing_row: Row(s) from ZS query result
        data_dict: The v1 record data dictionary

    Returns:
        True if record should be skipped, False otherwise
    """
    if existing_row and len(existing_row) > 0:
        row = existing_row[0]
        existing_upgrader_version = row.get("upgrader_version", "")
        existing_last_modified = row.get("last_modified", "")

        if existing_upgrader_version == upgrader_version and existing_last_modified == data_dict.get("last_modified"):
            return True
    return False


def update_cache_tracking(record_id: str, result: dict, existing_row: Optional[list]) -> None:
    """Update cache tracking data for a record (upsert by v1_id).

    Args:
        record_id: The v1 record ID
        result: Dictionary containing tracking data (v1_id, v2_id, upgrader_version, last_modified, status)
        existing_row: Unused; kept for interface compatibility
    """
    try:
        try:
            df = custom(TABLE_NAME)
        except ValueError:
            df = pd.DataFrame(columns=["v1_id", "v2_id", "upgrader_version", "last_modified", "status"])

        new_row = pd.DataFrame([{
            "v1_id": result["v1_id"],
            "v2_id": result.get("v2_id"),
            "upgrader_version": upgrader_version,
            "last_modified": result.get("last_modified", ""),
            "status": result["status"],
        }])

        # Remove existing row if present, then append updated row
        df = df[df["v1_id"] != str(record_id)]
        df = pd.concat([df, new_row], ignore_index=True)

        custom(TABLE_NAME, df=df)
        logging.info(f"Updated cache tracking for record {record_id}")
    except Exception as e:
        logging.error(f"Failed to update cache tracking for record {record_id}: {e}")


def run_one(record_id: str):
    """
    Upgrade a single record and update ZS tracking data

    Args:
        record_id: The v1 record ID to upgrade
    """
    logging.info(f"Processing single record ID: {record_id}")

    # Retrieve the v1 record
    records = client_v1.retrieve_docdb_records(filter_query={"_id": record_id})
    if not records:
        raise ValueError(f"Record ID {record_id} not found in v1 database")

    data_dict = records[0]

    # Check if we should skip this record
    existing_row = query_zs_record(record_id)
    if should_skip_record(existing_row, data_dict):
        logging.info(f"Record {record_id} already up-to-date, skipping")
        return

    # Upgrade the record
    record = None
    result = None
    try:
        record, result = upgrade_record(data_dict)
    except Exception as e:
        logging.error(f"Error upgrading record ID {record_id}: {e}")
        _delete_v2_record(data_dict)
        result = {
            "v1_id": str(record_id),
            "v2_id": None,
            "upgrader_version": upgrader_version,
            "last_modified": data_dict.get("last_modified"),
            "status": "failed",
        }

    # Upsert to DocumentDB if upgrade succeeded
    if record is not None:
        logging.info(f"Upserting record to DocumentDB: {record_id}")
        client_v2.upsert_one_docdb_record(record=record)
        logging.info(f"Successfully processed record {record_id}")
    else:
        logging.warning(f"Upgrade failed for record ID {record_id}")

    # Update ZS tracking data
    if result:
        update_cache_tracking(record_id, result, existing_row)


def run():
    """Run all records through the upgrader and store results in ZS"""
    # Get list of all record IDs from v1 database
    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1})
    record_ids = [record["_id"] for record in records_list]
    logging.info(f"Found {len(record_ids)} records to process")

    num_records = len(records_list)
    cached_records = []
    upgraded_records = []

    original_df = get_zs_data()

    # Wipe rows whose v1_id no longer exists in the v1 database
    if original_df is not None and len(record_ids) > 0:
        record_ids_set = set(str(rid) for rid in record_ids)
        original_df = original_df[original_df["v1_id"].isin(record_ids_set)]
        logging.info(f"Filtered original_df to {len(original_df)} records that exist in v1 database")

    upgrade_results = []

    # Cache 10 records at a time to reduce API calls
    for i in range(0, num_records, BATCH_SIZE):
        logging.info(f"Records: {i}/{num_records}")
        batch_ids = record_ids[i: i + BATCH_SIZE]
        cached_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": batch_ids}},
        )

        for data_dict in cached_records:

            record_id = data_dict["_id"]
            logging.info(f"Testing upgrade for record ID: {record_id}")

            # Skip assets that have already been successfully upgraded with this version
            v1_id = data_dict["_id"]
            if original_df is not None:
                if check_skip_conditions(data_dict, original_df):
                    continue

            try:
                record, result = upgrade_record(data_dict)
                upgraded_records.append(record)
                upgrade_results.append(result)
            except Exception as e:
                _delete_v2_record(data_dict)
                upgrade_results.append(
                    {
                        "v1_id": str(v1_id),
                        "v2_id": None,
                        "upgrader_version": upgrader_version,
                        "last_modified": data_dict.get("last_modified"),
                        "status": "failed",
                    }
                )
                record_id = data_dict["_id"]
                logging.error(f"Upgrade failed for record ID {record_id}: {e}")

        valid_records = [r for r in upgraded_records if r is not None]
        if len(valid_records) >= BATCH_SIZE:
            logging.info(f"Batch upserting {len(valid_records)} records to DocumentDB")
            client_v2.upsert_list_of_docdb_records(records=valid_records)
            upgraded_records.clear()

    # Process any remaining records at the end
    valid_records = [r for r in upgraded_records if r is not None]
    if valid_records:
        logging.info(f"Final batch upserting {len(valid_records)} records to DocumentDB")
        client_v2.upsert_list_of_docdb_records(records=valid_records)

    upload_to_forest(original_df, upgrade_results)


if __name__ == "__main__":
    run()
