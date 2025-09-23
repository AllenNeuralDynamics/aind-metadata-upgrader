"""Unit tests for the recursive_get_all_names function"""

import unittest
from enum import Enum
from aind_metadata_upgrader.utils.validators import recursive_get_all_names


class TestEnum(Enum):
    """Test enum for testing enum handling"""

    OPTION1 = "option1"
    OPTION2 = "option2"


class SimpleTestObject:
    """Simple test object with name attribute"""

    def __init__(self, name=None, value=None):
        """Initialize a SimpleTestObject.

        Args:
            name: Optional name attribute for the object
            value: Optional value attribute for the object
        """
        self.name = name
        self.value = value


class ComplexTestObject:
    """Complex test object with nested attributes"""

    def __init__(self, name=None, child=None, children=None, data=None):
        """Initialize a ComplexTestObject.

        Args:
            name: Optional name attribute for the object
            child: Optional child object attribute
            children: Optional list of child objects (defaults to empty list)
            data: Optional data attribute for additional storage
        """
        self.name = name
        self.child = child
        self.children = children or []
        self.data = data


class TestRecursiveGetAllNames(unittest.TestCase):
    """Test cases for recursive_get_all_names function"""

    def test_simple_object_with_name(self):
        """Test extracting name from a simple object"""
        obj = SimpleTestObject(name="test_object", value=42)
        result = recursive_get_all_names(obj)
        self.assertEqual(result, ["test_object"])

    def test_object_without_name(self):
        """Test object without name attribute"""
        obj = SimpleTestObject(value=42)
        result = recursive_get_all_names(obj)
        self.assertEqual(result, [])

    def test_object_with_none_name(self):
        """Test object with None as name"""
        obj = SimpleTestObject(name=None, value=42)
        result = recursive_get_all_names(obj)
        self.assertEqual(result, [])

    def test_object_with_non_string_name(self):
        """Test object with non-string name (should be ignored)"""
        obj = SimpleTestObject(name=123, value=42)
        result = recursive_get_all_names(obj)
        self.assertEqual(result, [])

    def test_nested_objects(self):
        """Test extracting names from nested objects"""
        child = SimpleTestObject(name="child_object", value=10)
        parent = ComplexTestObject(name="parent_object", child=child)
        result = recursive_get_all_names(parent)
        self.assertCountEqual(result, ["parent_object", "child_object"])

    def test_list_of_objects(self):
        """Test extracting names from a list of objects"""
        obj_list = [
            SimpleTestObject(name="item1", value=1),
            SimpleTestObject(name="item2", value=2),
            SimpleTestObject(value=3),  # no name
        ]
        result = recursive_get_all_names(obj_list)
        self.assertCountEqual(result, ["item1", "item2"])

    def test_object_with_list_of_children(self):
        """Test extracting names from object with list of children"""
        children = [SimpleTestObject(name="child1", value=1), SimpleTestObject(name="child2", value=2)]
        parent = ComplexTestObject(name="parent_with_children", children=children)
        result = recursive_get_all_names(parent)
        self.assertCountEqual(result, ["parent_with_children", "child1", "child2"])

    def test_simple_dictionary(self):
        """Test extracting name from a simple dictionary"""
        test_dict = {"name": "dict_name", "value": 42}
        result = recursive_get_all_names(test_dict)
        self.assertEqual(result, ["dict_name"])

    def test_nested_dictionaries(self):
        """Test extracting names from nested dictionaries"""
        nested_dict = {"name": "parent_dict", "child": {"name": "child_dict", "value": 10}}
        result = recursive_get_all_names(nested_dict)
        self.assertCountEqual(result, ["parent_dict", "child_dict"])

    def test_list_of_dictionaries(self):
        """Test extracting names from list of dictionaries"""
        dict_list = [
            {"name": "dict1", "type": "A"},
            {"name": "dict2", "type": "B"},
            {"value": "no_name"},  # no name field
        ]
        result = recursive_get_all_names(dict_list)
        self.assertCountEqual(result, ["dict1", "dict2"])

    def test_tuple_of_objects(self):
        """Test extracting names from tuple of objects"""
        obj_tuple = (SimpleTestObject(name="tuple_obj1"), SimpleTestObject(name="tuple_obj2"), {"name": "tuple_dict"})
        result = recursive_get_all_names(obj_tuple)
        self.assertCountEqual(result, ["tuple_obj1", "tuple_obj2", "tuple_dict"])

    def test_mixed_object_and_dictionary(self):
        """Test object containing dictionary attributes"""
        obj = ComplexTestObject(name="container_obj", data={"name": "nested_dict", "info": "data"})
        result = recursive_get_all_names(obj)
        self.assertCountEqual(result, ["container_obj", "nested_dict"])

    def test_deep_nesting(self):
        """Test deeply nested structure with mixed types"""
        complex_structure = {
            "name": "level1",
            "nested": {"name": "level2", "items": [{"name": "item_a", "value": 1}, {"name": "item_b", "value": 2}]},
        }
        result = recursive_get_all_names(complex_structure)
        self.assertCountEqual(result, ["level1", "level2", "item_a", "item_b"])

    def test_complex_mixed_structure(self):
        """Test complex structure mixing objects, dicts, lists, and tuples"""
        structure = {
            "name": "root",
            "data": [
                {"name": "dict_in_list", "items": ({"name": "dict_in_tuple"},)},
                SimpleTestObject(name="obj_in_list", value={"name": "dict_in_obj"}),
            ],
        }
        result = recursive_get_all_names(structure)
        expected = ["root", "dict_in_list", "dict_in_tuple", "obj_in_list", "dict_in_obj"]
        self.assertCountEqual(result, expected)

    def test_none_input(self):
        """Test None input"""
        result = recursive_get_all_names(None)
        self.assertEqual(result, [])

    def test_enum_input(self):
        """Test enum input (should be skipped)"""
        result = recursive_get_all_names(TestEnum.OPTION1)
        self.assertEqual(result, [])

    def test_primitive_types(self):
        """Test primitive types (should return empty)"""
        primitives = [42, 3.14, "hello", True, False]
        for primitive in primitives:
            with self.subTest(primitive=primitive):
                result = recursive_get_all_names(primitive)
                self.assertEqual(result, [])

    def test_empty_containers(self):
        """Test empty containers"""
        containers = [{}, [], ()]
        for container in containers:
            with self.subTest(container=container):
                result = recursive_get_all_names(container)
                self.assertEqual(result, [])

    def test_dictionary_with_non_string_name(self):
        """Test dictionary with non-string name (should be ignored)"""
        test_dict = {"name": 123, "value": "test"}
        result = recursive_get_all_names(test_dict)
        self.assertEqual(result, [])

    def test_real_world_device_structure(self):
        """Test with realistic device/instrument structure"""
        device_config = {
            "name": "main_rig",
            "devices": [
                {
                    "name": "camera1",
                    "components": [{"name": "sensor", "type": "CMOS"}, {"name": "lens", "focal_length": 50}],
                },
                {"name": "laser1", "settings": {"name": "power_controller", "max_power": 100}},
            ],
            "connections": ({"source": "camera1", "target": "computer"}, {"source": "laser1", "target": "camera1"}),
        }
        result = recursive_get_all_names(device_config)
        expected = ["main_rig", "camera1", "sensor", "lens", "laser1", "power_controller"]
        self.assertCountEqual(result, expected)

    def test_duplicate_names(self):
        """Test that duplicate names are preserved (not deduplicated)"""
        structure = [
            {"name": "device1"},
            {"name": "device1"},  # duplicate
            {"components": [{"name": "device1"}]},  # another duplicate
        ]
        result = recursive_get_all_names(structure)
        self.assertEqual(result, ["device1", "device1", "device1"])

    def test_nested_tuples_and_lists(self):
        """Test nested combinations of tuples and lists"""
        structure = [
            ({"name": "nested_in_tuple"}, SimpleTestObject(name="obj_in_tuple")),
            [{"name": "nested_in_list"}, SimpleTestObject(name="obj_in_list")],
        ]
        result = recursive_get_all_names(structure)
        expected = ["nested_in_tuple", "obj_in_tuple", "nested_in_list", "obj_in_list"]
        self.assertCountEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
