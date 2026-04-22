"""Upgrade a single record by _id and write the result to a JSON file."""

import argparse
import json
import os
import sys
import traceback

# Add src to path so we can import the upgrader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aind_metadata_upgrader.upgrade import Upgrade, CORE_FILES, CORE_MAPPING  # noqa: E402

RECORDS_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "records", "v1")


def load_record(record_id: str) -> dict:
    file_path = os.path.join(RECORDS_DIR, f"{record_id}.json")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Record not found: {file_path}")
    with open(file_path, "r") as f:
        return json.load(f)


def upgrade_core_files_individually(data_dict: dict) -> dict:
    """Attempt to upgrade each core file individually with skip_metadata_validation=True."""
    result = data_dict.copy()
    for core_file in CORE_FILES:
        if core_file not in data_dict or not data_dict[core_file]:
            continue
        target_key = CORE_MAPPING.get(core_file, core_file)
        try:
            # Build a minimal wrapper record with just this core file
            wrapper = {core_file: data_dict[core_file]}
            if "name" not in wrapper:
                wrapper["name"] = data_dict.get("name", "fakesubj_1000-01-01_00-00-00")
            if "location" not in wrapper:
                wrapper["location"] = data_dict.get("location", "fake_location_for_testing")
            upgraded = Upgrade(wrapper, skip_metadata_validation=True)
            upgraded_value = getattr(upgraded.metadata, target_key, None)
            if upgraded_value is not None:
                result[target_key] = (
                    upgraded_value.model_dump(mode="json")
                    if hasattr(upgraded_value, "model_dump")
                    else upgraded_value
                )
                print(f"  Individually upgraded: {core_file}")
            else:
                print(f"  No output for: {core_file}")
        except Exception:
            print(f"  Failed to individually upgrade {core_file}:")
            traceback.print_exc()
    return result


def main():
    parser = argparse.ArgumentParser(description="Upgrade a single metadata record by _id.")
    parser.add_argument("record_id", help="The _id of the record, e.g. 00318acb-e8f9-4072-ad32-0c5f2ee9798f")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output JSON file path (default: <record_id>_upgraded.json in current directory)",
    )
    args = parser.parse_args()

    record_id = args.record_id
    output_path = args.output or f"{record_id}_upgraded.json"

    print(f"Loading record: {record_id}")
    data_dict = load_record(record_id)

    # Add fake fields if missing (mirrors test_upgrade.py behaviour)
    if "name" not in data_dict:
        data_dict["name"] = "fakesubj_1000-01-01_00-00-00"
        print("  Added fake 'name' field")
    if "location" not in data_dict:
        data_dict["location"] = "fake_location_for_testing"
        print("  Added fake 'location' field")

    print("Attempting full upgrade...")
    try:
        upgraded = Upgrade(data_dict, skip_metadata_validation=False)
        result = upgraded.metadata.model_dump(mode="json")
        print("Full upgrade succeeded.")
    except Exception as e:
        print(f"Full upgrade failed: {e}")
        print("Falling back to per-core-file upgrade (skip_metadata_validation=True)...")
        result = upgrade_core_files_individually(data_dict)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Saved upgraded record to: {output_path}")


if __name__ == "__main__":
    main()
