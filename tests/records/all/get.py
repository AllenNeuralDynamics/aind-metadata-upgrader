"""Script to retrieve all records from the database and save them as JSON files"""

import json
import os
from aind_data_access_api.document_db import MetadataDbClient

# Configuration constants from test file
API_GATEWAY_HOST = "api.allenneuraldynamics.org"
DATABASE = "metadata_index"
COLLECTION = "data_assets"

BATCH_SIZE = 100


def get_records_batch(client, record_ids):
    """Get a batch of full records by their IDs"""
    try:
        records = client.retrieve_docdb_records(
            filter_query={"_id": {"$in": record_ids}},
            limit=0,
        )
        return records
    except Exception as e:
        print(f"Error retrieving batch: {e}")
        return []


def main():
    """Main function to retrieve records and save as JSON files"""

    # Initialize the client
    client = MetadataDbClient(
        host=API_GATEWAY_HOST,
        database=DATABASE,
        collection=COLLECTION,
    )

    # Get the current directory
    current_dir = os.path.dirname(__file__)

    print("Retrieving all record IDs from the database...")

    try:
        # First, get all record IDs
        id_records = client.retrieve_docdb_records(
            filter_query={},  # Empty filter to get all records
            projection={"_id": 1},
            limit=0,  # No limit to get all records
        )

        print(f"Retrieved {len(id_records)} record IDs")

        # Extract just the IDs
        record_ids = [record["_id"] for record in id_records]

        # Process records in batches
        total_saved = 0
        for i in range(0, len(record_ids), BATCH_SIZE):
            batch_ids = record_ids[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(record_ids) + BATCH_SIZE - 1) // BATCH_SIZE

            print(
                f"\nProcessing batch {batch_num}/{total_batches} ({len(batch_ids)} records)..."
            )

            # Get the full records for this batch
            records = get_records_batch(client, batch_ids)

            # Save each record in the batch
            for j, record in enumerate(records):
                try:
                    record_index = i + j
                    # Generate filename based on record name or index
                    filename = f"record_{record_index:04d}.json"
                    if "name" in record and record["name"]:
                        # Create a safe filename from the record name
                        safe_name = "".join(
                            c
                            for c in record["name"]
                            if c.isalnum() or c in (" ", "-", "_")
                        ).strip()
                        filename = f"{safe_name.replace(' ', '_')}.json"

                    # Save the record
                    file_path = os.path.join(current_dir, filename)
                    with open(file_path, "w") as f:
                        json.dump(record, f, indent=4)

                    total_saved += 1
                    print(
                        f"Saved record {record_index + 1}/{len(record_ids)}: {filename}"
                    )

                except Exception as e:
                    print(f"Error saving record {record_index + 1}: {e}")
                    continue

        print(f"\nCompleted! Saved {total_saved} records to {current_dir}")

    except Exception as e:
        print(f"Error retrieving records: {e}")
        return


if __name__ == "__main__":
    main()
