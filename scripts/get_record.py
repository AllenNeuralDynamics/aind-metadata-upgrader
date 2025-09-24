"""Helper to get a single record"""

from aind_data_access_api.document_db import MetadataDbClient
import json
import os

record_name = "behavior_789911_2025-07-11_19-47-52_processed_2025-09-23_17-06-54"

# Database configuration
API_GATEWAY_HOST = "api.allenneuraldynamics.org"
DATABASE = "metadata_index"
COLLECTION = "data_assets"

# Initialize the client
client = MetadataDbClient(
    host=API_GATEWAY_HOST,
    database=DATABASE,
    collection=COLLECTION,
)

# Retrieve the record
records = client.retrieve_docdb_records(
    filter_query={"name": record_name},
    limit=1,
)

if records:
    record = records[0]

    # Create tests/records/v1 directory relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    v1_dir = os.path.join(script_dir, "..", "tests", "records", "v1")
    os.makedirs(v1_dir, exist_ok=True)

    # Use _id field as filename
    record_id = record["_id"]
    output_filename = os.path.join(v1_dir, f"{record_id}.json")

    # Save the record as JSON
    with open(output_filename, "w") as output_file:
        json.dump(record, output_file, indent=4)

    print(f"Record saved to {output_filename}")
else:
    print(f"No record found with name: {record_name}")
