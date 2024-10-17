import unittest

from eth_utils.curried import ValidationError
from hexbytes import HexBytes

from hummingbot.connector.exchange.tegro.tegro_data_source import hash_domain, hash_eip712_message
from hummingbot.connector.exchange.tegro.tegro_messages import SignableMessage, encode_typed_data


class TestEncodeTypedData(unittest.TestCase):
    def setUp(self):
        self.domain_data = {
            "name": "Example Domain",
            "version": "1",
            "chainId": 1,
            "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"
        }

        self.message_types = {
            "CancelOrder": [
                {"name": "order_id", "type": "string"}
            ]
        }

        self.message_data = {
            "order_id": "123456"
        }

        self.full_message = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                "CancelOrder": [
                    {"name": "order_id", "type": "string"}
                ]
            },
            "primaryType": "CancelOrder",
            "domain": self.domain_data,
            "message": self.message_data
        }

    def test_encode_typed_data_basic(self):
        expected = SignableMessage(
            HexBytes(b"\x01"),
            hash_domain(self.domain_data),
            hash_eip712_message(self.message_types, self.message_data),
        )
        result = encode_typed_data(
            domain_data=self.domain_data,
            message_types=self.message_types,
            message_data=self.message_data
        )
        self.assertEqual(result, expected)

    def test_encode_typed_data_with_full_message(self):
        expected = SignableMessage(
            HexBytes(b"\x01"),
            hash_domain(self.domain_data),
            hash_eip712_message(self.message_types, self.message_data),
        )
        result = encode_typed_data(full_message=self.full_message)
        self.assertEqual(result, expected)

    def test_encode_typed_data_raises_value_error_with_extra_args(self):
        with self.assertRaises(ValueError):
            encode_typed_data(
                domain_data=self.domain_data,
                message_types=self.message_types,
                message_data=self.message_data,
                full_message=self.full_message
            )

    def test_encode_typed_data_raises_validation_error_on_mismatched_domain_fields(self):
        invalid_full_message = self.full_message.copy()
        invalid_full_message["domain"].pop("chainId")

        with self.assertRaises(ValidationError):
            encode_typed_data(full_message=invalid_full_message)

    def test_encode_typed_data_raises_validation_error_on_mismatched_primary_type(self):
        invalid_full_message = self.full_message.copy()
        invalid_full_message["primaryType"] = "InvalidType"

        with self.assertRaises(ValidationError):
            encode_typed_data(full_message=invalid_full_message)
