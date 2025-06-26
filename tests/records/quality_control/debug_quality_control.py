#!/usr/bin/env python3
"""
Debug script for QualityControl validation issues.
Specifically designed to catch "unhashable type dict" errors.
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from aind_data_schema.core.quality_control import QualityControl


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON file safely."""
    print(f"Loading JSON file: {file_path}")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        print(f"✓ Successfully loaded JSON with {len(str(data))} characters")
        return data
    except Exception as e:
        print(f"✗ Failed to load JSON: {e}")
        raise


def analyze_data_structure(data: Dict[str, Any], path: str = "root") -> None:
    """Recursively analyze the data structure to identify potential issues."""
    print(f"\n=== Analyzing structure at {path} ===")
    
    if isinstance(data, dict):
        print(f"Dict with keys: {list(data.keys())}")
        
        # Check for nested dicts in places where they might cause hashability issues
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"  {key}: dict with keys {list(value.keys())}")
                
                # Check if this dict has nested dicts that might be problematic
                if any(isinstance(v, dict) for v in value.values()):
                    print(f"    WARNING: {key} contains nested dicts")
                    
            elif isinstance(value, list):
                print(f"  {key}: list with {len(value)} items")
                if value:
                    first_item = value[0]
                    if isinstance(first_item, dict):
                        print(f"    First item is dict with keys: {list(first_item.keys())}")
                        
                        # Check for potential hashability issues in list items
                        for i, item in enumerate(value[:3]):  # Check first 3 items
                            if isinstance(item, dict):
                                nested_dicts = [k for k, v in item.items() if isinstance(v, dict)]
                                if nested_dicts:
                                    print(f"    Item {i} has nested dicts in keys: {nested_dicts}")
                                    
            else:
                print(f"  {key}: {type(value).__name__}")
                
    elif isinstance(data, list):
        print(f"List with {len(data)} items")
        if data and isinstance(data[0], dict):
            print(f"First item keys: {list(data[0].keys())}")


def validate_quality_control(data: Dict[str, Any]) -> None:
    """Attempt to validate the data as a QualityControl object."""
    print(f"\n=== Attempting QualityControl validation ===")
    
    try:
        # Try to create QualityControl object
        qc = QualityControl(**data)
        print(f"✓ Successfully created QualityControl object")
        print(f"  - Number of metrics: {len(qc.metrics)}")
        print(f"  - Schema version: {qc.schema_version}")
        print(f"  - Unique tags: {len(qc.tags)}")
        print(f"  - Unique modalities: {len(qc.modalities)}")
        
        # Now test model_dump() which is where the real issue might be
        test_model_dump(qc)
        
    except Exception as e:
        print(f"✗ Failed to create QualityControl object: {e}")
        print(f"Exception type: {type(e).__name__}")
        
        # Print full traceback for debugging
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Try to identify the specific issue
        error_str = str(e)
        if "unhashable type" in error_str.lower():
            print(f"\n🔍 UNHASHABLE TYPE ERROR DETECTED!")
            print(f"This often occurs when:")
            print(f"  1. Dictionaries are used in sets or as dictionary keys")
            print(f"  2. Lists containing dictionaries are used where hashable types are expected")
            print(f"  3. Complex nested structures cause issues with validation")
            
            # Try to pinpoint the issue by examining specific fields
            examine_potential_issues(data)


def test_model_dump(qc: QualityControl) -> None:
    """Test the model_dump() operation which often causes unhashable type errors."""
    print(f"\n=== Testing model_dump() operation ===")
    
    try:
        # Try basic model_dump()
        dumped = qc.model_dump()
        print(f"✓ Basic model_dump() successful - {len(str(dumped))} characters")
        
        # Try model_dump with exclude_none
        dumped_exclude_none = qc.model_dump(exclude_none=True)
        print(f"✓ model_dump(exclude_none=True) successful - {len(str(dumped_exclude_none))} characters")
        
        # Try model_dump_json
        json_str = qc.model_dump_json()
        print(f"✓ model_dump_json() successful - {len(json_str)} characters")
        
    except Exception as e:
        print(f"✗ model_dump() failed: {e}")
        print(f"Exception type: {type(e).__name__}")
        
        # Print full traceback for debugging
        print("\nFull traceback:")
        traceback.print_exc()
        
        error_str = str(e)
        if "unhashable type" in error_str.lower():
            print(f"\n🔍 UNHASHABLE TYPE ERROR IN MODEL_DUMP DETECTED!")
            print(f"This typically occurs when:")
            print(f"  1. The 'status' field contains unhashable types")
            print(f"  2. allow_tag_failures contains tuples or complex objects")
            print(f"  3. Computed properties create unhashable structures")
            
            # Investigate specific problematic fields
            investigate_dump_issues(qc)


def investigate_dump_issues(qc: QualityControl) -> None:
    """Try to isolate which field is causing the model_dump issue."""
    print(f"\n=== Investigating specific fields causing dump issues ===")
    
    # Test individual fields that are most likely to cause issues
    problematic_fields = []
    
    # Test status field (auto-computed)
    try:
        status_dict = qc.status
        print(f"Status field type: {type(status_dict)}")
        if status_dict:
            print(f"Status keys: {list(status_dict.keys())}")
            # Try to convert status to dict manually
            import json
            json.dumps(status_dict, default=str)
            print(f"✓ Status field is JSON serializable")
    except Exception as e:
        print(f"✗ Status field causes issues: {e}")
        problematic_fields.append("status")
    
    # Test allow_tag_failures field
    try:
        atf = qc.allow_tag_failures
        print(f"allow_tag_failures type: {type(atf)}, length: {len(atf)}")
        if atf:
            print(f"First few items: {atf[:3]}")
            for i, item in enumerate(atf):
                if isinstance(item, tuple):
                    print(f"  Item {i} is tuple: {item}")
                elif not isinstance(item, (str, int, float, bool)):
                    print(f"  Item {i} is potentially problematic: {type(item)} = {item}")
    except Exception as e:
        print(f"✗ allow_tag_failures field causes issues: {e}")
        problematic_fields.append("allow_tag_failures")
    
    # Test tags property (computed)
    try:
        tags = qc.tags
        print(f"Tags property: {tags}")
        # Check if tags contain any unhashable types
        for tag in tags:
            if not isinstance(tag, (str, int, float, bool)):
                print(f"  Potentially problematic tag: {type(tag)} = {tag}")
    except Exception as e:
        print(f"✗ Tags property causes issues: {e}")
        problematic_fields.append("tags")
    
    # Test modalities property (computed)
    try:
        modalities = qc.modalities
        print(f"Modalities property: {modalities}")
        # Check if modalities contain any unhashable types
        for mod in modalities:
            if hasattr(mod, '__dict__'):
                print(f"  Modality object: {type(mod)} = {mod}")
    except Exception as e:
        print(f"✗ Modalities property causes issues: {e}")
        problematic_fields.append("modalities")
    
    if problematic_fields:
        print(f"\n🎯 Problematic fields identified: {problematic_fields}")
    else:
        print(f"\n🤔 No obvious problematic fields found - the issue might be deeper")


def examine_potential_issues(data: Dict[str, Any]) -> None:
    """Examine specific fields that commonly cause hashability issues."""
    print(f"\n=== Examining potential problem areas ===")
    
    # Check metrics field specifically
    if 'metrics' in data:
        metrics = data['metrics']
        print(f"Metrics field: {type(metrics)} with {len(metrics) if isinstance(metrics, list) else 'N/A'} items")
        
        if isinstance(metrics, list) and metrics:
            first_metric = metrics[0]
            print(f"First metric keys: {list(first_metric.keys()) if isinstance(first_metric, dict) else 'Not a dict'}")
            
            # Check for problematic fields in metrics
            problematic_fields = []
            for i, metric in enumerate(metrics[:5]):  # Check first 5 metrics
                if isinstance(metric, dict):
                    # Check for fields that might contain unhashable types
                    for field_name, field_value in metric.items():
                        if isinstance(field_value, (dict, list)):
                            if isinstance(field_value, dict) and any(isinstance(v, (dict, list)) for v in field_value.values()):
                                problematic_fields.append(f"metric[{i}].{field_name}")
                            elif isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                                problematic_fields.append(f"metric[{i}].{field_name}")
            
            if problematic_fields:
                print(f"Potentially problematic fields: {problematic_fields}")
    
    # Check allow_tag_failures field
    if 'allow_tag_failures' in data:
        atf = data['allow_tag_failures']
        print(f"allow_tag_failures: {type(atf)} = {atf}")
        if isinstance(atf, list):
            for i, item in enumerate(atf):
                if isinstance(item, (dict, list)):
                    print(f"  Item {i} is {type(item)}: {item}")


def main():
    """Main debug function."""
    print("🔍 QualityControl Debug Script")
    print("=" * 50)
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    
    # Try both v1 and v2 files
    for version in ['v1', 'v2']:
        json_file = script_dir / f"{version}.json"
        
        if not json_file.exists():
            print(f"❌ File not found: {json_file}")
            continue
            
        print(f"\n{'='*20} Processing {version}.json {'='*20}")
        
        try:
            # Load the JSON data
            data = load_json_file(json_file)
            
            # Analyze the structure
            analyze_data_structure(data)
            
            # Try to validate as QualityControl
            validate_quality_control(data)
            
        except Exception as e:
            print(f"❌ Critical error processing {version}.json: {e}")
            traceback.print_exc()
        
        print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
