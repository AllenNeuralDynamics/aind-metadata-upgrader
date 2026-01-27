"""Sync code to upgrade metadata from v1 to v2 and store results in RDS"""

import logging
import os
from typing import Optional
from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient
from aind_data_access_api.rds_tables import RDSCredentials
from aind_data_access_api.rds_tables import Client
import pandas as pd
from aind_metadata_upgrader import __version__ as upgrader_version


DOCDB_HOST = os.getenv("DOCDB_HOST", "api.allenneuraldynamics.org")
BATCH_SIZE = 100
CHUNK_SIZE = 1000


# docdb
client_v1 = MetadataDbClient(
    host=DOCDB_HOST,
    version="v1",
)

client_v2 = MetadataDbClient(
    host=DOCDB_HOST,
    version="v2",
)


# redshift settings
# we'll store v1_id, v2_id, upgrade_version, status
REDSHIFT_AWS_SECRET_NAME = os.getenv("REDSHIFT_AWS_SECRET_NAME", "/aind/prod/redshift/credentials/readwrite")
REDSHIFT_TABLE_NAME = os.getenv("REDSHIFT_TABLE_NAME", "metadata_upgrade_status_prod")

try:
    rds_client = Client(
        credentials=RDSCredentials(aws_secrets_name=REDSHIFT_AWS_SECRET_NAME),
    )
except Exception:
    # For testing purposes, allow this to fail silently
    rds_client = None


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
            v2_id = response.json.get("insertedId", "")
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


def get_rds_data() -> Optional[pd.DataFrame]:
    """Retrieve existing upgrade status data from RDS"""
    try:
        df = rds_client.read_table(REDSHIFT_TABLE_NAME)
    except Exception as e:
        logging.error(f"(METADATA VALIDATOR): Error reading from RDS table {REDSHIFT_TABLE_NAME}: {e}")
        df = None

    if df is not None and ("v1_id" not in df.columns or len(df) < 1):
        logging.info("(METADATA VALIDATOR): No previous validation results found, starting fresh")
        df = None

    return df


def upload_to_rds_helper(df: pd.DataFrame):
    """Upload upgrade results to RDS, chunking if necessary"""
    logging.info(f"(METADATA VALIDATOR) Uploading {len(df)} records to RDS")

    if len(df) <= CHUNK_SIZE:
        logging.info("(METADATA VALIDATOR) No chunking required for RDS")
        rds_client.overwrite_table_with_df(df, REDSHIFT_TABLE_NAME)
    else:
        # chunk into CHUNK_SIZE row chunks
        logging.info("(METADATA VALIDATOR) Chunking required for RDS")
        # Process first chunk
        first_chunk = pd.DataFrame(df.iloc[:CHUNK_SIZE])
        rds_client.overwrite_table_with_df(first_chunk, REDSHIFT_TABLE_NAME)

        # Process remaining chunks
        for i in range(CHUNK_SIZE, len(df), CHUNK_SIZE):
            end_idx = min(i + CHUNK_SIZE, len(df))
            chunk = pd.DataFrame(df.iloc[i:end_idx])
            rds_client.append_df_to_table(chunk, REDSHIFT_TABLE_NAME)


def check_skip_conditions(data_dict: dict, original_df: Optional[pd.DataFrame]) -> bool:
    """Check if a record should be skipped based on existing RDS data"""
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


def upload_to_rds(original_df: Optional[pd.DataFrame], upgrade_results: list[dict]):
    """Upload upgrade results to RDS"""
    # Upload any remaining tracking data
    if upgrade_results:
        logging.info(f"Uploading final batch of {len(upgrade_results)} tracking records to RDS")
        batch_df = pd.DataFrame(upgrade_results)
        try:
            if original_df is not None:
                # Merge with existing data
                combined_df = pd.concat([original_df, batch_df], ignore_index=True)
                # Remove duplicates, keeping the latest entry for each v1_id
                combined_df = combined_df.drop_duplicates(subset=["v1_id"], keep="last")
                upload_to_rds_helper(combined_df)
            else:
                upload_to_rds_helper(batch_df)
        except Exception as e:
            logging.warning(f"Failed to upload final tracking data to RDS: {e}")
    else:
        logging.info("(METADATA VALIDATOR) No upgrade results to write to RDS")


def query_rds_record(record_id: str) -> Optional[list]:
    """Query RDS for a specific record by v1_id.

    Args:
        record_id: The v1 record ID to query

    Returns:
        List of matching rows (typically 0 or 1 row), or None if query fails
    """
    try:
        query = (
            f"SELECT v1_id, v2_id, upgrader_version, last_modified, status FROM "
            f"{REDSHIFT_TABLE_NAME} WHERE v1_id = '{record_id}'"
        )
        result = rds_client.execute_query(query)
        if result:
            # Convert SQLAlchemy Row objects to dictionaries
            return [dict(row._mapping) for row in result.fetchall()]
        return None
    except Exception as e:
        logging.warning(f"Error querying RDS for record {record_id}: {e}")
        return None


def should_skip_record(existing_row: Optional[list], data_dict: dict) -> bool:
    """Check if a record should be skipped based on existing RDS data.

    Args:
        existing_row: Row(s) from RDS query result
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


def update_rds_tracking(record_id: str, result: dict, existing_row: Optional[list]) -> None:
    """Update RDS tracking data for a record using SQL INSERT or UPDATE.

    Args:
        record_id: The v1 record ID
        result: Dictionary containing tracking data (v1_id, v2_id, upgrader_version, last_modified, status)
        existing_row: Row(s) from RDS query result, used to determine INSERT vs UPDATE
    """
    try:
        v1_id = result["v1_id"]
        v2_id = result.get("v2_id")
        status = result["status"]
        last_modified = result.get("last_modified", "")

        # Check if row exists
        if existing_row and len(existing_row) > 0:
            # Update existing row
            set_command = (
                "v2_id = '{v2_id}', upgrader_version = '{upgrader_version}',"
                "last_modified = '{last_modified}', status = '{status}'"
            )

            update_query = f"""
            UPDATE {REDSHIFT_TABLE_NAME}
            SET {set_command}
            WHERE v1_id = '{v1_id}'
            """
            rds_client.execute_query(update_query)
            logging.info(f"Updated RDS tracking for record {record_id}")
        else:
            # Insert new row
            insert_query = f"""
            INSERT INTO {REDSHIFT_TABLE_NAME} (v1_id, v2_id, upgrader_version, last_modified, status)
            VALUES ('{v1_id}', '{v2_id}', '{upgrader_version}', '{last_modified}', '{status}')
            """
            rds_client.execute_query(insert_query)
            logging.info(f"Inserted RDS tracking for record {record_id}")
    except Exception as e:
        logging.error(f"Failed to update RDS tracking for record {record_id}: {e}")


def run_one(record_id: str):
    """
    Upgrade a single record and update RDS tracking data

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
    existing_row = query_rds_record(record_id)
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

    # Update RDS tracking data
    if result:
        update_rds_tracking(record_id, result, existing_row)


def run():
    """Run all records through the upgrader and store results in RDS"""
    # Get list of all record IDs from v1 database
    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1})

    num_records = len(records_list)
    cached_records = []
    upgraded_records = []

    original_df = get_rds_data()

    upgrade_results = []

    # Cache 10 records at a time to reduce API calls
    for i in range(0, num_records, BATCH_SIZE):
        logging.info(f"Records: {i}/{num_records}")
        batch = records_list[i: i + BATCH_SIZE]  # fmt: skip
        cached_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": [record["_id"] for record in batch]}},
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

    upload_to_rds(original_df, upgrade_results)


if __name__ == "__main__":
    run()
