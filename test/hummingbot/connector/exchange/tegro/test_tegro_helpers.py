import unittest

from hummingbot.connector.exchange.tegro.tegro_data_source import (
    is_0x_prefixed_hexstr,
    is_array_type,
    parse_core_array_type,
    parse_parent_array_type,
)
from hummingbot.connector.exchange.tegro.tegro_helpers import _get_eip712_solidity_types


class TestSolidityTypes(unittest.TestCase):
    def setUp(self):
        self.solidity_types = _get_eip712_solidity_types()

    def test_get_eip712_solidity_types(self):
        expected_types = [
            "bool", "address", "string", "bytes", "uint", "int",
            *[f"int{(x + 1) * 8}" for x in range(32)],
            *[f"uint{(x + 1) * 8}" for x in range(32)],
            *[f"bytes{x + 1}" for x in range(32)]
        ]
        self.assertEqual(self.solidity_types, expected_types)

    def test_is_array_type(self):
        self.assertTrue(is_array_type("uint256[]"))
        self.assertTrue(is_array_type("Person[3]"))
        self.assertFalse(is_array_type("uint256"))
        self.assertFalse(is_array_type("Person"))

    def test_is_0x_prefixed_hexstr(self):
        self.assertTrue(is_0x_prefixed_hexstr("0x123456"))
        self.assertFalse(is_0x_prefixed_hexstr("123456"))
        self.assertFalse(is_0x_prefixed_hexstr("0x12345G"))
        self.assertFalse(is_0x_prefixed_hexstr("hello"))

    def test_parse_core_array_type(self):
        self.assertEqual(parse_core_array_type("Person[][]"), "Person")
        self.assertEqual(parse_core_array_type("uint256[]"), "uint256")
        self.assertEqual(parse_core_array_type("Person"), "Person")

    def test_parse_parent_array_type(self):
        self.assertEqual(parse_parent_array_type("Person[3][1]"), "Person[3]")
        self.assertEqual(parse_parent_array_type("uint256[]"), "uint256")
        self.assertEqual(parse_parent_array_type("Person"), "Person")


if __name__ == "__main__":
    unittest.main()
