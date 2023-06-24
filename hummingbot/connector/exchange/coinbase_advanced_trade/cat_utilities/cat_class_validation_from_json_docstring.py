import inspect
import random
import re
import unittest
from datetime import datetime
from enum import Enum

from pydantic.error_wrappers import ValidationError

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    extract_json_from_docstring,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_pydantic_for_json import (
    PydanticForJsonConfig,
)


def generate_substitute(value):
    if isinstance(value, str):
        if value.lower() in ['true', 'false']:
            return random.choice([True, False])
        # Generating numbers to not fail the dates passed as strings
        return "".join(random.choice('123456789') for _ in range(10))
    elif isinstance(value, bool):
        return random.choice([True, False])
    elif isinstance(value, int):
        # This could be a date, so let's make it big enough
        return random.randint(946706401, 1687550733)
    elif isinstance(value, float):
        # This could be a date, so let's make it big enough
        return round(random.uniform(946706401, 1687550733), 2)
    elif value is None:
        return None
    else:
        raise Exception("Unhandled data type")


class ClassValidationFromJsonDocstring:
    class TestSuite(unittest.TestCase):
        class_under_test = None
        docstring = None

        @classmethod
        def setUpClass(cls) -> None:
            cls.docstring = inspect.getdoc(cls.class_under_test)

        def setUp(self) -> None:
            self.maxDiff = None

            self.json_struct = extract_json_from_docstring(self.docstring)
            try:
                self.instance = self.class_under_test(**self.json_struct)
            except TypeError as e:
                self.fail(f"JSON data does not match the structure of {self.class_under_test.__name__}"
                          f"\n\tReason: {str(e)}"
                          f"\n\tJSON: {self.json_struct}")

        def generate_random_path_and_substitute(self, json_struct, path=None):
            if path is None:
                path = []

            keys = [k for k in json_struct.keys()]

            random_key = random.choice(keys)
            path.append(random_key)

            if isinstance(json_struct[random_key], dict):
                return self.generate_random_path_and_substitute(json_struct[random_key], path)
            elif isinstance(json_struct[random_key], list):
                index = random.randint(0, len(json_struct[random_key]) - 1)
                path.append(index)
                if isinstance(json_struct[random_key][index], dict):
                    return self.generate_random_path_and_substitute(json_struct[random_key][index], path)
                else:
                    substitute = generate_substitute(json_struct[random_key][index])
                    return self.path_to_dict(path, substitute)
            else:
                substitute = generate_substitute(json_struct[random_key])
                return self.path_to_dict(path, substitute)

        def path_to_dict(self, path, substitute):
            if isinstance(path[0], int):
                # this is a list index, build a list instead of a dict
                if len(path) == 1:
                    return [substitute]
                return [self.path_to_dict(path[1:], substitute) if i == path[0] else None for i in range(path[0] + 1)]
            elif len(path) == 1:
                return {path[0]: substitute}
            else:
                return {path[0]: self.path_to_dict(path[1:], substitute)}

        def check_type(self, instance, struct):
            """Recursively check types for the instance."""
            for k, v in struct.items():
                if "__fields__" in dir(instance):
                    attr_name = None
                    for attr in instance.__fields__:
                        if k == instance.__fields__[attr].alias:
                            attr_name = attr
                            break
                    if attr_name is None:
                        raise Exception(f"Attribute {k} not found in {instance.__class__.__name__}")
                    attr = getattr(instance, attr_name)
                else:
                    attr = getattr(instance, k)
                # print(f"Checking {k}\n\ttype {type(attr)}\n\t{v}")
                if isinstance(v, dict):
                    if isinstance(attr, PydanticForJsonConfig):
                        # The attribute is a BaseModel, check its fields
                        self.check_type(attr, v)
                    else:
                        # For plain dict, check its type
                        self.assertIsInstance(attr, dict), f"{k} is not a dict"
                elif isinstance(v, list):
                    if isinstance(attr, PydanticForJsonConfig):
                        # The attribute is a list of BaseModel, check each of them
                        for el, val in zip(attr, v):
                            self.check_type(el, val)
                    else:
                        # For plain list, check its type
                        self.assertIsInstance(attr, (list, tuple, set)), f"{k} is not a list"
                else:
                    # If the attribute is an Enum, compare its value instead of its type
                    if isinstance(attr, Enum):
                        self.assertEqual(attr.value, v), f"{k} enum value does not match"
                    elif isinstance(attr, datetime):
                        # Check if the datetime string matches the 'Z' format
                        if isinstance(v, str):
                            if (
                                    (m := re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z", v)) or
                                    (m := re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).000Z", v)) or
                                    (m := re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).000000Z", v))
                            ):
                                self.assertEqual(m.group(1),
                                                 attr.strftime("%Y-%m-%dT%H:%M:%S"),
                                                 f"{k} datetime strftime does not match {v}")
                            else:
                                self.assertTrue(v[:-1] in attr.strftime("%Y-%m-%dT%H:%M:%S.%f"), f"{k} datetime timestamp does not match")
                        else:
                            self.assertEqual(v, attr.timestamp(), f"{k} datetime timestamp does not match")
                    else:
                        # Check the field type
                        self.assertIsInstance(attr, type(v)), f"{k} is not of type {type(v)}"

        def test_to_dict_for_json(self):
            self.assertEqual(self.json_struct, self.instance.to_dict_for_json())

        def test_to_dict_for_json_exact_match_of_keys(self):
            self.assertEqual(set(self.json_struct.keys()), set(self.instance.to_dict_for_json().keys()))

        def test_types(self):
            """Test if all fields have the correct types."""
            self.check_type(self.instance, self.json_struct)

        def test_field_substitution(self):
            def flatten_dict(d, parent_key='', sep='.'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    elif isinstance(v, list):
                        for i, item in enumerate(v):
                            new_key = f"{parent_key}{k}[{i}]" if parent_key else f"{k}[{i}]"
                            if isinstance(item, dict):
                                items.extend(flatten_dict(item, new_key, sep=sep).items())
                            else:
                                items.append((new_key, item))
                    else:
                        items.append((new_key, v))
                return dict(items)

            def get_nested_attr(obj, attr_list):
                if not isinstance(attr_list, list):
                    attr_list = [a for a in re.split(r'[\[\].]', attr_list) if a]
                for attr in attr_list:
                    if attr.isdigit():
                        obj = obj[int(attr)]  # treat as an index
                    else:
                        obj = getattr(obj, attr)  # treat as an attribute name
                return obj

            substitute_dict = self.generate_random_path_and_substitute(self.json_struct)
            flattened_substitute_dict = flatten_dict(substitute_dict)
            if any((isinstance(get_nested_attr(self.instance, v), Enum) for v in flattened_substitute_dict)):
                # The value created will never match one of the pre-defined Enum str values
                # This test would fail, but proves that the value has changed from the original
                # Thus testing that the creation raises a Validation Error is sufficient
                with self.assertRaises(Exception):
                    self.class_under_test(**substitute_dict)
                return

            substituted_json = self.class_under_test.dict_sample_from_json_docstring(substitute_dict)
            try:
                substituted_instance = self.class_under_test(**substituted_json)
            except ValidationError as e:
                if "limit" in e.errors()[0]["loc"]:
                    # The value created will never match one of the pre-defined Enum str values
                    # This test would fail, but proves that the value has changed from the original
                    # Thus testing that the creation raises a Validation Error is sufficient
                    pass
                else:
                    self.fail(f"Failed to create instance from substituted json: {e}")

            for path, substituted_value in flattened_substitute_dict.items():
                original_value = get_nested_attr(self.instance, path)
                if not isinstance(original_value, bool):
                    self.assertNotEqual(original_value, substituted_value)
                    continue
                substituted_value_instance = get_nested_attr(substituted_instance, path)
                self.assertEqual(str(substituted_value_instance), str(substituted_value))
