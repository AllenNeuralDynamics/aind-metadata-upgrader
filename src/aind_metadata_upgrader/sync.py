import logging
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

rds_client = Client(
    credentials=RDSCredentials(aws_secrets_name=REDSHIFT_SECRETS),
)


def run():
    """Test the upgrade process"""
    # Get list of all record IDs from v1 database
    records_list = client_v1.retrieve_docdb_records(filter_query={}, projection={"_id": 1}, limit=10)

    num_records = len(records_list)
    cached_records = []
    upgraded_records = []

    try:
        original_df = rds_client.read_table(RDS_TABLE_NAME)
    except Exception as e:
        logging.error(f"(METADATA VALIDATOR): Error reading from RDS table {RDS_TABLE_NAME}: {e}")
        original_df = None

    if original_df is not None and ("v1_id" not in original_df.columns or len(original_df) < 1):
        logging.info("(METADATA VALIDATOR): No previous validation results found, starting fresh")
        original_df = None

    upgrade_results = []

    # Cache 10 records at a time to reduce API calls
    for i in range(0, num_records, BATCH_SIZE):
        print(f"Records: {i}/{num_records}")
        batch = records_list[i : i + BATCH_SIZE]
        cached_records = client_v1.retrieve_docdb_records(
            filter_query={"_id": {"$in": [record["_id"] for record in batch]}},
        )

        for data_dict in cached_records:

            print(f"\n\nTesting upgrade for record ID: {data_dict["_id"]}")

            # Skip assets that have already been successfully upgraded with this version
            v1_id = data_dict["_id"]
            if original_df is not None:
                existing = original_df[original_df["v1_id"] == str(v1_id)]
                if (
                    len(existing) > 0
                    and existing.iloc[0]["upgrader_version"] == upgrader_version
                    and existing.iloc[0]["status"] == "success"
                ):
                    print(f"Skipping already successfully upgraded record ID {v1_id}")
                    continue

            try:
                upgraded = Upgrade(data_dict)

                if upgraded:

                    location = upgraded.metadata.location

                    records = client_v2.retrieve_docdb_records(
                        filter_query={"location": location},
                        limit=1,
                    )
                    if len(records) == 0:
                        print(f"Inserting new upgraded record to DocumentDB: {upgraded.metadata.name}")
                        client_v2.insert_one_docdb_record(
                            record=upgraded.metadata.model_dump(),
                        )
                        # Recover the _id field
                        new_record = client_v2.retrieve_docdb_records(
                            filter_query={"location": location},
                            limit=1,
                        )
                        v2_id = new_record[0]["_id"]
                    else:
                        v2_id = records[0]["_id"]
                        record_data = upgraded.metadata.model_dump()
                        record_data["_id"] = v2_id
                        upgraded_records.append(record_data)
                        print(f"Batch updating existing record in DocumentDB: {upgraded.metadata.name}")

                    upgrade_results.append(
                        {
                            "v1_id": str(v1_id),
                            "v2_id": str(v2_id),
                            "upgrader_version": upgrader_version,
                            "status": "success",
                        }
                    )
                else:
                    upgrade_results.append(
                        {
                            "v1_id": str(v1_id),
                            "v2_id": None,
                            "upgrader_version": upgrader_version,
                            "status": "failed",
                        }
                    )
                    print(f"Upgrade returned None for record ID {v1_id}")
            except Exception as e:
                upgrade_results.append(
                    {
                        "v1_id": str(v1_id),
                        "v2_id": None,
                        "upgrader_version": upgrader_version,
                        "status": "failed",
                    }
                )
                print(f"Upgrade failed for record ID {data_dict["_id"]}: {e}")

        if len(upgraded_records) >= BATCH_SIZE:
            print(f"Batch upserting {len(upgraded_records)} records to DocumentDB")
            client_v2.upsert_list_of_docdb_records(
                records=upgraded_records,
            )
            upgraded_records.clear()

    # Handle any remaining upgraded_records that weren't processed in batch
    if len(upgraded_records) > 0:
        print(f"Final batch upserting {len(upgraded_records)} records to DocumentDB")
        client_v2.upsert_list_of_docdb_records(
            records=upgraded_records,
        )
        upgraded_records.clear()

    if not upgrade_results:
        logging.info("(METADATA VALIDATOR) No upgrade results to write to RDS")
        return

    final_df = pd.DataFrame(upgrade_results)

    if len(final_df) <= CHUNK_SIZE:
        rds_client.overwrite_table_with_df(final_df, RDS_TABLE_NAME)
    else:
        # chunk into CHUNK_SIZE row chunks
        logging.info("(METADATA VALIDATOR) Chunking required for RDS")
        # Process first chunk
        first_chunk = pd.DataFrame(final_df.iloc[:CHUNK_SIZE])
        rds_client.overwrite_table_with_df(first_chunk, RDS_TABLE_NAME)

        # Process remaining chunks
        for i in range(CHUNK_SIZE, len(final_df), CHUNK_SIZE):
            end_idx = min(i + CHUNK_SIZE, len(final_df))
            chunk = pd.DataFrame(final_df.iloc[i:end_idx])
            rds_client.append_df_to_table(chunk, RDS_TABLE_NAME)


if __name__ == "__main__":
    run()
