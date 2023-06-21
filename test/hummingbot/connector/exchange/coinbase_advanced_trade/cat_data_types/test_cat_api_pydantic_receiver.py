import copy
import inspect
import unittest
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

# from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import *  # noqa: F401, F403
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    extract_json_from_docstring,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_pydantic_for_json import (
    PydanticMockableForJson,
)


class DummyPhoneNumbers(BaseModel):
    type: str
    number: str


class TestMockableResponse(unittest.TestCase):
    class DummyClass(PydanticMockableForJson):
        """```json
        {
            "name": "John Doe",
            "age": 30,
            "isAlive": true,
            "height": null,
            "address": {
                "street": "1234 Park St",
                "city": "San Jose",
                "state": "CA",
                "postalCode": "95130"
            },
            "phoneNumbers": [
                {
                    "type": "home",
                    "number": "408 123-4567"
                }
            ],
            "fixedPhoneNumbers": [
                {
                    "type": "home",
                    "number": "408 123-4567"
                }
            ]
        }
        ```
        """
        name: str
        age: int
        isAlive: bool
        height: Optional[float]
        address: Dict[str, str]
        phoneNumbers: List[DummyPhoneNumbers]
        fixedPhoneNumbers: Tuple[DummyPhoneNumbers, ...]

    def setUp(self):
        self.class_under_test = self.DummyClass
        self.docstring = inspect.getdoc(self.class_under_test)

    def test_sample_from_json_doc(self):
        # Test substitute with single value
        substitutes = {"name": "Jane Doe"}
        instance = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        self.assertEqual(instance["name"], "Jane Doe", "Value substitution did not work as expected.")
        self.assertEqual(self.DummyClass(**instance).name, "Jane Doe", "Value substitution did not work as expected.")

        # Test substitute with nested value
        substitutes = {"address": {"city": "Los Angeles"}}
        instance = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        self.assertEqual(instance["address"]["city"], "Los Angeles",
                         "Nested value substitution did not work as expected.")
        self.assertEqual(self.DummyClass(**instance).address["city"], "Los Angeles",
                         "Nested value substitution did not work as expected.")

        # Test substitute with list of values
        substitutes = {"phoneNumbers": [{"number": "408 123-1234"}, {"type": "office", "number": "408 123-1235"}]}
        instance = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        self.assertEqual(instance["phoneNumbers"][1]["number"], "408 123-1235",
                         "Second value in list substitution did not work as expected.")
        self.assertEqual(instance["phoneNumbers"][0]["number"], "408 123-1234",
                         "First value in list substitution did not work as expected.")
        self.assertEqual(self.DummyClass(**instance).phoneNumbers[1].number, "408 123-1235",
                         "Second value in list substitution did not work as expected.")

        # Test substitute a tuple with list of values
        substitutes = {"fixedPhoneNumbers": [{"type": "home", "number": "408 123-1234"},
                                             {"type": "office", "number": "408 123-1235"}]}
        instance = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        self.assertEqual(instance["fixedPhoneNumbers"][1]["number"], "408 123-1235",
                         "Second value in list substitution did not work as expected.")
        self.assertEqual(instance["fixedPhoneNumbers"][0]["number"], "408 123-1234",
                         "First value in list substitution did not work as expected.")
        self.assertEqual(self.DummyClass(**instance).fixedPhoneNumbers[1].number, "408 123-1235",
                         "Second value in list substitution did not work as expected.")

    def test_substitute_with(self):
        json_struct = extract_json_from_docstring(self.docstring)
        substitutes = {"name": "Jane Doe"}

        # Substituting single value
        self.class_under_test._substitute_with(json_struct, substitutes)
        self.assertEqual(json_struct["name"], "Jane Doe", "Value substitution did not work as expected.")
        self.assertEqual(self.class_under_test(**json_struct).name, "Jane Doe",
                         "Value substitution did not work as expected.")

        # Substituting nested value
        substitutes = {"address": {"city": "Los Angeles"}}
        self.class_under_test._substitute_with(json_struct, substitutes)
        self.assertEqual(json_struct["address"]["city"], "Los Angeles",
                         "Nested value substitution did not work as expected.")
        self.assertEqual(self.class_under_test(**json_struct).address["city"], "Los Angeles",
                         "Nested value substitution did not work as expected.")
        substitutes = {
            "phoneNumbers": [{"type": "home", "number": "408 123-1234"}, {"type": "office", "number": "408 123-1235"}]}
        self.class_under_test._substitute_with(json_struct, substitutes)
        self.assertEqual(json_struct["phoneNumbers"][0]["number"], "408 123-1234",
                         "First value in list substitution did not work as expected.")
        self.assertEqual(json_struct["phoneNumbers"][1]["number"], "408 123-1235",
                         "Second value in list substitution did not work as expected.")
        self.assertEqual(self.class_under_test(**json_struct).phoneNumbers[1].number, "408 123-1235",
                         "Second value in list substitution did not work as expected.")

    def test_extract_json_from_docstring(self):
        json_struct = extract_json_from_docstring(self.docstring)
        self.assertTrue(isinstance(json_struct, dict), "Expected output to be a dictionary.")
        self.assertTrue("name" in json_struct, "Expected 'name' to be in the dictionary.")

    def test_substitute_with_no_substitution(self):
        sample_data = self.class_under_test.dict_sample_from_json_docstring({})
        original_data = copy.deepcopy(sample_data)
        self.assertEqual(sample_data, original_data, "Data changed despite no substitution")

    def test_substitute_with_non_existent_field(self):
        substitutes = {"non_existent_field": "5.23"}
        sample_data = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        with self.assertRaises(KeyError):
            _ = sample_data["non_existent_field"]

    def test_substitute_with_various_types(self):
        substitutes = {"name": "John Doe", "age": 25, "phoneNumbers": [{"type": "home", "number": "6.23"}],
                       "isAlive": True}
        sample_data = self.class_under_test.dict_sample_from_json_docstring(substitutes)
        self.assertEqual(sample_data["name"], "John Doe", "String substitution did not work as expected.")
        self.assertEqual(sample_data["age"], 25, "Integer substitution did not work as expected.")
        self.assertEqual(sample_data["phoneNumbers"][0]["number"], "6.23",
                         "Nested value substitution did not work as expected.")
        self.assertEqual(sample_data["isAlive"], True, "Boolean substitution did not work as expected.")
        self.assertEqual(self.class_under_test(**sample_data).name, "John Doe", "String substitution did not work as "
                                                                                "expected.")


if __name__ == "__main__":
    unittest.main()
