"""Sync code to upgrade metadata from v1 to v2 and store results in RDS"""

import logging
from typing import Optional
from aind_metadata_upgrader.upgrade import Upgrade
from aind_data_access_api.document_db import MetadataDbClient
from aind_data_access_api.rds_tables import RDSCredentials
from aind_data_access_api.rds_tables import Client
import pandas as pd
from aind_metadata_upgrader import __version__ as upgrader_version


API_GATEWAY_HOST = "api.allenneuraldynamics.org"
BATCH_SIZE = 100
CHUNK_SIZE = 1000


# docdb
client_v1 = MetadataDbClient(
    host=API_GATEWAY_HOST,
    version="v1",
)

client_v2 = MetadataDbClient(
    host=API_GATEWAY_HOST,
    version="v2",
)


# redshift settings
# we'll store v1_id, v2_id, upgrade_version, status
REDSHIFT_SECRETS = "/aind/prod/redshift/credentials/readwrite"
RDS_TABLE_NAME = "metadata_upgrade_status_prod"

try:
    rds_client = Client(
        credentials=RDSCredentials(aws_secrets_name=REDSHIFT_SECRETS),
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
            print(f"Inserting new upgraded record to DocumentDB: {upgraded.metadata.name}")
            response = client_v2.insert_one_docdb_record(
                record=upgraded.metadata.model_dump(),
            )
            v2_id = response.json.get("insertedId", "")
            new_record = None  # already inserted
        else:
            v2_id = records[0]["_id"]
            new_record = upgraded.metadata.model_dump()
            new_record["_id"] = v2_id
            print(f"Batch updating existing record in DocumentDB: {upgraded.metadata.name}")

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
        df = rds_client.read_table(RDS_TABLE_NAME)
    except Exception as e:
        logging.error(f"(METADATA VALIDATOR): Error reading from RDS table {RDS_TABLE_NAME}: {e}")
        df = None

    if df is not None and ("v1_id" not in df.columns or len(df) < 1):
        logging.info("(METADATA VALIDATOR): No previous validation results found, starting fresh")
        df = None

    return df


def upload_to_rds(df: pd.DataFrame):
    """Upload upgrade results to RDS, chunking if necessary"""

    if len(df) <= CHUNK_SIZE:
        rds_client.overwrite_table_with_df(df, RDS_TABLE_NAME)
    else:
        # chunk into CHUNK_SIZE row chunks
        logging.info("(METADATA VALIDATOR) Chunking required for RDS")
        # Process first chunk
        first_chunk = pd.DataFrame(df.iloc[:CHUNK_SIZE])
        rds_client.overwrite_table_with_df(first_chunk, RDS_TABLE_NAME)

        # Process remaining chunks
        for i in range(CHUNK_SIZE, len(df), CHUNK_SIZE):
            end_idx = min(i + CHUNK_SIZE, len(df))
            chunk = pd.DataFrame(df.iloc[i:end_idx])
            rds_client.append_df_to_table(chunk, RDS_TABLE_NAME)


def run():
    """Test the upgrade process"""
    # Get list of all record IDs from v1 database
    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1})

    num_records = len(records_list)
    cached_records = []
    upgraded_records = []

    original_df = get_rds_data()

    upgrade_results = []

    # Cache 10 records at a time to reduce API calls
    for i in range(0, num_records, BATCH_SIZE):
        print(f"Records: {i}/{num_records}")
        batch = records_list[i : i + BATCH_SIZE]
        cached_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": [record["_id"] for record in batch]}},
        )

        for data_dict in cached_records:

            record_id = data_dict["_id"]
            print(f"\n\nTesting upgrade for record ID: {record_id}")

            # Skip assets that have already been successfully upgraded with this version
            v1_id = data_dict["_id"]
            if original_df is not None:
                existing = original_df[original_df["v1_id"] == str(v1_id)]
                # Skip if already attempted upgrade with this version and last_modified has not changed
                if (
                    len(existing) > 0
                    and existing.iloc[0]["upgrader_version"] == upgrader_version
                    and existing.iloc[0]["last_modified"] == data_dict.get("last_modified")
                ):
                    print(f"Skipping already successfully upgraded record ID {v1_id}")
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
                print(f"Upgrade failed for record ID {record_id}: {e}")

        valid_records = [r for r in upgraded_records if r is not None]
        if len(valid_records) >= BATCH_SIZE:
            print(f"Batch upserting {len(valid_records)} records to DocumentDB")
            client_v2.upsert_list_of_docdb_records(records=valid_records)
            upgraded_records.clear()

    # Process any remaining records at the end
    valid_records = [r for r in upgraded_records if r is not None]
    if valid_records:
        print(f"Final batch upserting {len(valid_records)} records to DocumentDB")
        client_v2.upsert_list_of_docdb_records(records=valid_records)

    if not upgrade_results:
        logging.info("(METADATA VALIDATOR) No upgrade results to write to RDS")
        return

    final_df = pd.DataFrame(upgrade_results)
    upload_to_rds(final_df)


if __name__ == "__main__":
    run()
