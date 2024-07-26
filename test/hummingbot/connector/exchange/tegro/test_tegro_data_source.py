import unittest

from eth_utils import keccak

from hummingbot.connector.exchange.tegro.tegro_data_source import (
    encode_data,
    encode_field,
    encode_type,
    find_type_dependencies,
    get_primary_type,
    hash_domain,
    hash_eip712_message,
    hash_struct,
    hash_type,
)


class TestEIP712(unittest.TestCase):

    def setUp(self):
        self.sample_types = {
            "Person": [
                {"name": "name", "type": "string"},
                {"name": "wallet", "type": "address"},
            ],
            "Mail": [
                {"name": "from", "type": "Person"},
                {"name": "to", "type": "Person"},
                {"name": "contents", "type": "string"},
            ],
        }

        self.sample_data = {
            "from": {
                "name": "Alice",
                "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"  # noqa: mock
            },
            "to": {
                "name": "Bob",
                "wallet": "0xDeaDbeefdEAdbeefdEadbEEFdeadbeEFdEaDbeeF"  # noqa: mock
            },
            "contents": "Hello, Bob!"
        }

    def test_get_primary_type(self):
        primary_type = get_primary_type(self.sample_types)
        self.assertEqual(primary_type, "Mail")

    def test_encode_field(self):
        encoded = encode_field(self.sample_types, "name", "string", "Alice")
        self.assertEqual(encoded[0], "bytes32")
        self.assertEqual(encoded[1], keccak(b"Alice"))

    def test_find_type_dependencies(self):
        dependencies = find_type_dependencies("Mail", self.sample_types)
        self.assertIn("Person", dependencies)
        self.assertIn("Mail", dependencies)

    def test_encode_type(self):
        encoded_type = encode_type("Mail", self.sample_types)
        expected = "Mail(Person from,Person to,string contents)Person(string name,address wallet)"
        self.assertEqual(encoded_type, expected)

    def test_hash_type(self):
        hashed_type = hash_type("Mail", self.sample_types)
        expected = keccak(b"Mail(Person from,Person to,string contents)Person(string name,address wallet)")
        self.assertEqual(hashed_type, expected)

    def test_encode_data(self):
        encoded_data = encode_data("Mail", self.sample_types, self.sample_data)
        self.assertTrue(isinstance(encoded_data, bytes))

    def test_hash_struct(self):
        hashed_struct = hash_struct("Mail", self.sample_types, self.sample_data)
        self.assertTrue(isinstance(hashed_struct, bytes))

    def test_hash_eip712_message(self):
        hashed_message = hash_eip712_message(self.sample_types, self.sample_data)
        self.assertTrue(isinstance(hashed_message, bytes))

    def test_hash_domain(self):
        domain_data = {
            "name": "Ether Mail",
            "version": "1",
            "chainId": 1,
            "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",  # noqa: mock
            "salt": "0xdecafbaddecafbaddecafbaddecafbaddecafbaddecafbaddecafbaddecafbad"  # noqa: mock
        }
        hashed_domain = hash_domain(domain_data)
        self.assertTrue(isinstance(hashed_domain, bytes))
