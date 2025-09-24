"""Script to bulk upgrade metadata records from v1 to v2"""

from typing import List

from aind_data_access_api.document_db import MetadataDbClient
from aind_metadata_upgrader.upgrade import Upgrade

# Database configuration
V1_API_GATEWAY_HOST = "api.allenneuraldynamics.org"
V1_DATABASE = "metadata_index"
V1_COLLECTION = "data_assets"

V2_API_GATEWAY_HOST = "api.allenneuraldynamics.org"
V2_DATABASE = "metadata_index_v2"
V2_COLLECTION = "data_assets"


def bulk_upgrade(asset_names: List[str]) -> None:
    """Download and upgrade a list of asset names from v1 to v2"""

    # Initialize clients
    v1_client = MetadataDbClient(
        host=V1_API_GATEWAY_HOST,
        database=V1_DATABASE,
        collection=V1_COLLECTION,
    )

    v2_client = MetadataDbClient(
        host=V2_API_GATEWAY_HOST,
        database=V2_DATABASE,
        collection=V2_COLLECTION,
    )

    for asset_name in asset_names:
        print(f"Processing {asset_name}...")

        # Download from v1
        records = v1_client.retrieve_docdb_records(
            filter_query={"name": asset_name},
            limit=1,
        )

        if not records:
            records = v1_client.retrieve_docdb_records(
                filter_query={"name": {"$regex": asset_name}},
                limit=1,
            )

        if not records:
            print(f"  Not found in v1: {asset_name}")
            continue

        record = records[0]

        # Upgrade
        try:
            upgraded = Upgrade(record)
        except Exception as e:
            print(f"  Upgrade failed for {asset_name}: {e}")
            continue

        # Upsert to v2
        location = upgraded.metadata.location
        existing_records = v2_client.retrieve_docdb_records(
            filter_query={"location": location},
            limit=1,
        )

        if existing_records:
            # Update existing
            record_data = upgraded.metadata.model_dump(mode="json")
            record_data["_id"] = existing_records[0]["_id"]
            v2_client.upsert_one_docdb_record(record=record_data)
            print(f"  Updated: {asset_name}")
        else:
            # Insert new
            v2_client.insert_one_docdb_record(record=upgraded.metadata.model_dump(mode="json"))
            print(f"  Inserted: {asset_name}")


asset_names = [
    "ecephys_655565_2023-04-03_13-34-16",
    "ecephys_655565_2023-04-03_13-34-16_nwb",
    "ecephys_655565_2023-04-05_16-17-25",
    "ecephys_655565_2023-04-05_16-17-25_nwb",
    "ecephys_655568_2023-05-01_15-26-47",
    "ecephys_655568_2023-05-01_15-26-47_nwb",
    "ecephys_655568_2023-05-03_15-21-12",
    "ecephys_655568_2023-05-03_15-21-12_nwb",
    "ecephys_655571_2023-05-09_13-53-48",
    "ecephys_655571_2023-05-09_13-53-48_nwb",
    "ecephys_655571_2023-05-15_13-39-49",
    "ecephys_655571_2023-05-15_13-39-49_nwb",
    "ecephys_655572_2023-05-09_15-03-29",
    "ecephys_655572_2023-05-09_15-03-29_nwb",
    "ecephys_655572_2023-05-15_15-06-36",
    "ecephys_655572_2023-05-15_15-06-36_nwb",
    "ecephys_660104_2023-07-24_18-18-13",
    "ecephys_660104_2023-07-24_18-18-13_nwb",
    "ecephys_661398_2023-03-31_17-01-09",
    "ecephys_661398_2023-03-31_17-01-09_nwb",
    "ecephys_661398_2023-04-03_15-47-29",
    "ecephys_661398_2023-04-03_15-47-29_nwb",
    "ecephys_661398_2023-04-06_16-02-15",
    "ecephys_661398_2023-04-06_16-02-15_nwb",
    "ecephys_662913_2023-07-20_16-15-45",
    "ecephys_662913_2023-07-20_16-15-45_nwb",
    "ecephys_666721_2023-05-09_11-01-03",
    "ecephys_666721_2023-05-09_11-01-03_nwb",
    "ecephys_666721_2023-05-12_16-15-36",
    "ecephys_666721_2023-05-12_16-15-36_nwb",
    "ecephys_666859_2023-06-13_14-19-34",
    "ecephys_666859_2023-06-13_14-19-34_nwb",
    "ecephys_666861_2023-05-23_10-04-20",
    "ecephys_666861_2023-05-23_10-04-20_nwb",
    "ecephys_666861_2023-05-24_14-30-05",
    "ecephys_666861_2023-05-24_14-30-05_nwb",
    "ecephys_671646_2023-07-31_15-21-40",
    "ecephys_671646_2023-07-31_15-21-40_nwb",
    "ecephys_674005_2023-08-08_15-39-38",
    "ecephys_674005_2023-08-08_15-39-38_nwb",
    "ecephys_674005_2023-08-10_13-15-14",
    "ecephys_674005_2023-08-10_13-15-14_nwb",
    "ecephys_678449_2023-08-28_17-53-41",
    "ecephys_678449_2023-08-28_17-53-41_nwb",
    "ecephys_678577_2023-11-06_15-58-49",
    "ecephys_678577_2023-11-06_15-58-49_nwb",
    "ecephys_682033_2023-10-26_14-21-51",
    "ecephys_682033_2023-10-26_14-21-51_nwb",
    "ecephys_682085_2023-10-03_16-42-49",
    "ecephys_682085_2023-10-03_16-42-49_nwb",
    "ecephys_684156_2023-10-11_17-45-08",
    "ecephys_684156_2023-10-11_17-45-08_nwb",
    "ecephys_684156_2023-10-13_16-56-59",
    "ecephys_684156_2023-10-13_16-56-59_nwb",
    "ecephys_692497_2023-12-11_16-20-55",
    "ecephys_692497_2023-12-11_16-20-55_nwb",
    "ecephys_692497_2023-12-15_16-29-04",
    "ecephys_692497_2023-12-15_16-29-04_nwb",
    "ecephys_694471_2023-12-11_14-51-57",
    "ecephys_694471_2023-12-11_14-51-57_nwb",
    "ecephys_694471_2023-12-15_15-26-01",
    "ecephys_694471_2023-12-15_15-26-01_nwb",
    "ecephys_694473_2023-11-28_15-23-23",
    "ecephys_694473_2023-11-28_15-23-23_nwb",
    "ecephys_697577_2024-02-13_16-24-10",
    "ecephys_697577_2024-02-13_16-24-10_nwb",
    "ecephys_704242_2024-04-30_17-13-29",
    "ecephys_704242_2024-04-30_17-13-29_nwb",
    "ecephys_704242_2024-05-02_16-51-50",
    "ecephys_704242_2024-05-02_16-51-50_nwb",
    "ecephys_715287_2024-04-24_15-24-43",
    "ecephys_715287_2024-04-24_15-24-43_nwb",
    "ecephys_715290_2024-05-09_15-39-23",
    "ecephys_715290_2024-05-09_15-39-23_nwb",
    "ecephys_715339_2024-05-08_16-09-35",
    "ecephys_715339_2024-05-08_16-09-35_nwb",
    "ecephys_719093_2024-05-13_16-42-41",
    "ecephys_719093_2024-05-13_16-42-41_nwb",
    "ecephys_719093_2024-05-15_15-01-10",
    "ecephys_719093_2024-05-15_15-01-10_nwb",
]


if __name__ == "__main__":
    bulk_upgrade(asset_names)
