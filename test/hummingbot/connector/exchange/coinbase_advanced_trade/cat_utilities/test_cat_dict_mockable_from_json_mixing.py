import random
import unittest
from typing import Dict, Optional
from unittest.mock import patch

from pydantic import BaseModel

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
    DictMethodMockableFromJsonOneOfManyDocMixin,
    extract_json_from_docstring,
)


class TestDictMethodMockableFromJsonDocMixin(unittest.TestCase):
    # Define a class to test with
    class TestClassWithoutJsonDoc(DictMethodMockableFromJsonDocMixin, BaseModel):
        name: str
        age: int

        def to_dict_for_json(self) -> Dict:
            return self.dict()

    class TestClassWithoutDictMethod:
        name: str
        age: int

    # Define a class to test with
    class TestClass(DictMethodMockableFromJsonDocMixin, BaseModel):
        """
        ```json
        {
            "name": "Alice",
            "age": 25
        }
        ```
        """
        name: str
        age: int

        def to_dict_for_json(self) -> Dict:
            return self.dict()

    class TestClassNested(DictMethodMockableFromJsonDocMixin, BaseModel):
        """
        ```json
        {
            "name": "Alice",
            "age": 25,
            "address": {
                "street": "123 Main St",
                "city": "Springfield"
            }
        }
        ```
        """
        name: str
        age: int
        address: Dict[str, str]

        def to_dict_for_json(self) -> Dict:
            return self.dict()

    def setUp(self):
        self.test_class_instance = self.TestClass(name="Bob", age=30)

    def test_extract_json_from_docstring(self):
        result = extract_json_from_docstring(self.TestClass.__doc__)
        self.assertIsNotNone(result)
        self.assertEqual(result, {"name": "Alice", "age": 25})

    def test_sample_from_json_doc(self):
        sample = self.TestClass.dict_sample_from_json_docstring()
        self.assertEqual(sample, {"name": "Alice", "age": 25})

    def test_sample_from_json_doc_with_substitutes(self):
        sample = self.TestClass.dict_sample_from_json_docstring({"name": "Charlie", "age": 35})
        self.assertEqual(sample, {"name": "Charlie", "age": 35})

    def test_substitute_with(self):
        substitutes = {"name": "David", "age": 40}
        result = self.test_class_instance._substitute_with(self.test_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, {"name": "David", "age": 40})

    def test_substitute_with_partial_substitutes(self):
        substitutes = {"name": "Edward"}
        result = self.test_class_instance._substitute_with(self.test_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, {"name": "Edward", "age": 30})

    def test_sample_from_json_doc_nested(self):
        sample = self.TestClassNested.dict_sample_from_json_docstring()
        expected = {"name": "Alice", "age": 25, "address": {"street": "123 Main St", "city": "Springfield"}}
        self.assertEqual(sample, expected)

    def test_sample_from_json_doc_with_substitutes_nested(self):
        sample = self.TestClassNested.dict_sample_from_json_docstring(
            {"name": "Charlie", "age": 35, "address": {"city": "Shelbyville"}})
        expected = {"name": "Charlie", "age": 35, "address": {"street": "123 Main St", "city": "Shelbyville"}}
        self.assertEqual(sample, expected)

    def test_substitute_with_non_existent_keys(self):
        substitutes = {"non_existent_key": "value"}
        result = self.test_class_instance._substitute_with(self.test_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, self.test_class_instance.to_dict_for_json())  # Should remain unchanged

    def test_class_without_json_in_docstring(self):
        sample = self.TestClassWithoutJsonDoc.dict_sample_from_json_docstring()
        self.assertIsNone(sample)

    def test_class_without_dict_method(self):
        with self.assertRaises(AttributeError):
            self.TestClassWithoutDictMethod.sample_from_json_doc()


class _Address(DictMethodMockableFromJsonDocMixin, BaseModel):
    """
    ```json
    {
        "city": "New York",
        "street": "Broadway",
        "zip": "10027"
    }
    ```
    """
    city: str = None
    street: str = None
    zip: str = None

    def to_dict_for_json(self) -> Dict:
        return self.dict(exclude_none=True)


class _OptionClass(DictMethodMockableFromJsonOneOfManyDocMixin, BaseModel):
    """
    ```json
    {
        "primary":
        {
            "city": "New York",
            "street": "Broadway",
            "zip": "10027"
        },
        "secondary":
        {
            "city": "Dilan",
            "street": "Snowy",
            "zip": "98765"
        },
        "vacation":
        {
            "city": "Honolulu",
            "street": "Beach",
            "zip": "12345"
        }
    }
    ```
    """
    primary: Optional[_Address]
    secondary: Optional[_Address]
    vacation: Optional[_Address]

    def to_dict_for_json(self) -> Dict:
        return self.dict(exclude_none=True)


class _PersonNestedOption(DictMethodMockableFromJsonDocMixin, BaseModel):
    """
    ```json
    {
        "name": "Alice",
        "age": 25,
        "address": {
            "primary": {
                "city": "New York",
                "street": "Broadway",
                "zip": "10027"
            }
        }
    }
    ```
    """
    name: str
    age: int
    address: _OptionClass

    def to_dict_for_json(self) -> Dict:
        return self.dict(exclude_none=True)


class TestDictMethodMockableFromPartialJsonDocMixin(unittest.TestCase):
    class TestPartialClass(DictMethodMockableFromJsonOneOfManyDocMixin, BaseModel):
        """
        ```json
        {
            "name": "Alice",
            "age": 25,
            "city": "Springfield"
        }
        ```
        """
        name: str = None
        age: int = None
        city: str = None

        def to_dict_for_json(self) -> Dict:
            return self.dict(exclude_none=True)

    def setUp(self):
        self.test_partial_class_instance = self.TestPartialClass(name="Bob", age=30, city="Shelbyville")

    def test_partial_sample_from_json_doc(self):
        with patch.object(random, 'choice', return_value="name"):
            sample = self.TestPartialClass.dict_sample_from_json_docstring()
        self.assertEqual(sample, {"name": "Alice"})

    def test_partial_sample_with_substitute(self):
        with patch.object(random, 'choice', return_value="name"):
            sample = self.TestPartialClass.dict_sample_from_json_docstring({"name": "Charlie"})
        self.assertEqual(sample, {"name": "Charlie"})

    def test_partial_substitute_with(self):
        substitutes = {"name": "David", "age": 40, "city": "Capital City"}
        result = self.test_partial_class_instance._substitute_with(
            self.test_partial_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, {"name": "David", "age": 40, "city": "Capital City"})

    def test_partial_substitute_with_missing_substitutes(self):
        substitutes = {"name": "Edward"}
        result = self.test_partial_class_instance._substitute_with(
            self.test_partial_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, {"name": "Edward", "age": 30, "city": "Shelbyville"})

    def test_partial_substitute_with_non_existent_keys(self):
        substitutes = {"non_existent_key": "value"}
        result = self.test_partial_class_instance._substitute_with(
            self.test_partial_class_instance.to_dict_for_json(), substitutes)
        self.assertEqual(result, self.test_partial_class_instance.to_dict_for_json())

    def test_option_class_sample_from_json_doc(self):
        with patch.object(random, 'choice', return_value="primary"):
            sample = _OptionClass.dict_sample_from_json_docstring()
        self.assertEqual(
            {
                "primary":
                    {
                        "city": "New York",
                        "street": "Broadway",
                        "zip": "10027"
                    },
            },
            sample)

        with patch.object(random, 'choice', return_value="secondary"):
            sample = _OptionClass.dict_sample_from_json_docstring()
        self.assertEqual(
            {
                "secondary":
                    {
                        "city": "Dilan",
                        "street": "Snowy",
                        "zip": "98765"
                    },
            },
            sample)

    def test_option_class_sample_from_json_doc_with_substitutes(self):
        test_substitutes = {
            "vacation": {
                "street": "Palm Tree",
            }
        }
        with patch.object(random, 'choice', return_value="primary"):
            sample = _OptionClass.dict_sample_from_json_docstring(test_substitutes)
        self.assertEqual(
            {
                "vacation":
                    {
                        "city": "Honolulu",
                        "street": "Palm Tree",
                        "zip": "12345"
                    },
            },
            sample)

    def test_nested_option_class_sample_from_json_doc_with_substitutes(self):
        test_substitutes = {
            "address": {
                "vacation": {
                    "street": "Palm Tree",
                }
            }
        }
        with patch.object(random, 'choice', return_value="primary"):
            sample = _PersonNestedOption.dict_sample_from_json_docstring(test_substitutes)
        self.assertEqual(
            {
                "name": "Alice",
                "age": 25,
                "address": {
                    "vacation": {
                        "city": "Honolulu",
                        "street": "Palm Tree",
                        "zip": "12345"
                    }
                }
            },
            sample)


if __name__ == '__main__':
    unittest.main()
