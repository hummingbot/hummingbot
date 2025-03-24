import json
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import patch

import pytest
from eth_abi import encode
from hexbytes import HexBytes
from web3 import Web3

from hummingbot.connector.other.derive_common_utils import MAX_INT_256, MIN_INT_256, SignedAction, decimal_to_big_int


@dataclass
class ModuleData:
    pass


@dataclass
class TradeModuleData(ModuleData):
    asset_address: str
    sub_id: int
    limit_price: Decimal
    amount: Decimal
    max_fee: Decimal
    recipient_id: int
    is_bid: bool

    def to_abi_encoded(self):
        return encode(
            ["address", "uint", "int", "int", "uint", "uint", "bool"],
            [
                Web3.to_checksum_address(self.asset_address),
                self.sub_id,
                decimal_to_big_int(self.limit_price),
                decimal_to_big_int(self.amount),
                decimal_to_big_int(self.max_fee),
                self.recipient_id,
                self.is_bid,
            ],
        )

    def to_json(self):
        return {
            "limit_price": str(self.limit_price),
            "amount": str(self.amount),
            "max_fee": str(self.max_fee),
        }


@pytest.mark.parametrize(
    "input_decimal,expected_int",
    [
        (Decimal("1"), 10 ** 18),  # happy path: positive integer
        (Decimal("-1"), -(10 ** 18)),  # happy path: negative integer
        (Decimal("1.2345"), 1234500000000000000),  # happy path: positive float
        (Decimal("-1.2345"), -1234500000000000000),  # happy path: negative float
        (Decimal("0"), 0),  # edge case: zero
        (Decimal("0.000000000000000001"), 1),  # edge case: smallest positive value
        (Decimal("-0.000000000000000001"), -1),  # edge case: smallest negative value
    ],
    ids=[
        "positive_integer",
        "negative_integer",
        "positive_float",
        "negative_float",
        "zero",
        "smallest_positive",
        "smallest_negative",
    ],
)
def test_decimal_to_big_int_happy_path(input_decimal, expected_int):
    actual_int = decimal_to_big_int(input_decimal)

    assert actual_int == expected_int


@pytest.mark.parametrize(
    "input_decimal",
    [
        (Decimal(MIN_INT_256 // int(10 ** 18))),  # edge case: min value
        (Decimal(MAX_INT_256 // int(10 ** 18))),  # edge case: max value
        (Decimal((MIN_INT_256 + 1) // int(10 ** 18))),  # edge case: min value + 1
        (Decimal((MAX_INT_256 - 1) // int(10 ** 18))),  # edge case: max value - 1
    ],
    ids=["min_value", "max_value", "min_value_plus_one", "max_value_minus_one"],
)
def test_decimal_to_big_int_edge_cases(input_decimal):
    actual_int = decimal_to_big_int(input_decimal)

    assert actual_int == int(input_decimal * Decimal(10 ** 18))


@pytest.mark.parametrize(
    "input_decimal",
    [
        (Decimal((MIN_INT_256 - 1) // int(10 ** 18))),  # error case: less than min value
        (Decimal((MAX_INT_256 + 1) // int(10 ** 18))),  # error case: greater than max value
    ],
    ids=["less_than_min", "greater_than_max"],
)
def test_decimal_to_big_int_error_cases(input_decimal):
    with pytest.raises(ValueError) as e:
        decimal_to_big_int(input_decimal)
    assert f"resulting integer value must be between {MIN_INT_256} and {MAX_INT_256}" in str(e.value)


@pytest.mark.parametrize(
    "asset_address, sub_id, limit_price, amount, max_fee, recipient_id, is_bid, expected_json",
    [
        (
            "0x1234567890abcdef1234567890abcdef12345678",
            1,
            Decimal("100.50"),
            Decimal("1.2345"),
            Decimal("0.01"),
            2,
            True,
            '{"limit_price": "100.50", "amount": "1.2345", "max_fee": "0.01"}',
        ),  # happy path
        (
            "0x1234567890abcdef1234567890abcdef12345678",
            0,
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            0,
            False,
            '{"limit_price": "0", "amount": "0", "max_fee": "0"}',
        ),  # edge case: zero values
        (
            "0x1234567890abcdef1234567890abcdef12345678",
            -1,
            Decimal("-1.5"),
            Decimal("-0.0001"),
            Decimal("-0.000000000000000001"),
            -2,
            True,
            '{"limit_price": "-1.5", "amount": "-0.0001", "max_fee": "-1E-18"}',
        ),  # edge case: negative values
    ],
    ids=["happy_path", "zero_values", "negative_values"],
)
def test_trade_module_data_to_json(
        asset_address, sub_id, limit_price, amount, max_fee, recipient_id, is_bid, expected_json
):
    trade_data = TradeModuleData(
        asset_address=asset_address,
        sub_id=sub_id,
        limit_price=limit_price,
        amount=amount,
        max_fee=max_fee,
        recipient_id=recipient_id,
        is_bid=is_bid,
    )
    json_output = trade_data.to_json()

    assert json.loads(expected_json) == json_output


@pytest.mark.parametrize(
    "asset_address, sub_id, limit_price, amount, max_fee, recipient_id, is_bid",
    [
        (
            "0x1234567890abcdef1234567890abcdef12345678",  # noqa: mock
            1,
            Decimal("100.50"),
            Decimal("1.2345"),
            Decimal("0.01"),
            2,
            True,
        ),  # happy path
        (
            "0x1234567890abcdef1234567890abcdef12345678",  # noqa: mock
            0,
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            0,
            False,
        ),  # edge case: zero values
        (
            "0x1234567890abcdef1234567890abcdef12345678",  # noqa: mock
            -1,
            Decimal("-1.5"),
            Decimal("-0.0001"),
            Decimal("-0.000000000000000001"),
            -2,
            True,
        ),  # edge case: negative values
    ],
    ids=["happy_path", "zero_values", "negative_values"],
)
def test_trade_module_data_to_abi_encoded(
        asset_address, sub_id, limit_price, amount, max_fee, recipient_id, is_bid
):
    trade_data = TradeModuleData(
        asset_address=asset_address,
        sub_id=sub_id,
        limit_price=limit_price,
        amount=amount,
        max_fee=max_fee,
        recipient_id=recipient_id,
        is_bid=is_bid,
    )
    encoded_data = trade_data.to_abi_encoded()

    assert isinstance(encoded_data, bytes)


@pytest.fixture
def signed_action():
    return SignedAction(
        subaccount_id=1,
        owner="0xOwner",
        signer="0xSigner",
        signature_expiry_sec=1695836058,
        nonce=1695836058725001,
        module_address="0xModuleAddress",
        module_data=ModuleData(),
        DOMAIN_SEPARATOR="0x42",  # Dummy value for testing
        ACTION_TYPEHASH="0x43",  # Dummy value for testing
    )


@patch("eth_account.signers.local.LocalAccount.unsafe_sign_hash")
def test_sign(mock_sign_hash, signed_action):
    mock_sign_hash.return_value.signature = HexBytes("0xSignature")

    signature = signed_action.sign("0xPrivateKey")

    assert signature == "0x5369676e6174757265"  # noqa: mock


@pytest.mark.parametrize(
    "domain_separator, action_typehash, expected_typed_data_hash",
    [
        (
            "0x42",
            "0x43",
            HexBytes("0x5369676e6174757265"),  # noqa: mock
        ),  # Happy path
    ],
    ids=["happy_path"],
)
@patch("web3.Web3.keccak")
def test__to_typed_data_hash(mock_keccak, signed_action, domain_separator, action_typehash, expected_typed_data_hash):
    signed_action.DOMAIN_SEPARATOR = domain_separator
    signed_action.ACTION_TYPEHASH = action_typehash
    mock_keccak.return_value = expected_typed_data_hash

    typed_data_hash = signed_action._to_typed_data_hash()

    assert typed_data_hash == expected_typed_data_hash


@patch("web3.Web3.keccak")
def test__get_action_hash(mock_keccak, signed_action):
    mock_keccak.return_value = HexBytes("0xActionHash")

    action_hash = signed_action._get_action_hash()

    assert action_hash == HexBytes("0x416374696f6e48617368")  # noqa: mock


def test_to_json(signed_action):
    signed_action.signature = "0xSignature"

    json_output = signed_action.to_json()

    expected_json = {
        "subaccount_id": 1,
        "nonce": 1695836058725001,
        "signer": "0xSigner",
        "signature_expiry_sec": 1695836058,
        "signature": "0xSignature",
    }
    assert json_output == expected_json


@pytest.mark.parametrize(
    "signature, signer, expected_exception",
    [
        ("0xValidSignature", "0xSigner", None),  # Happy path
        ("0xInvalidSignature", "0xSigner", ValueError),  # Invalid signature
    ],
    ids=["valid_signature", "invalid_signature"],
)
@patch("eth_account.Account._recover_hash")
def test_validate_signature(mock_recover_hash, signed_action, signature, signer, expected_exception):
    signed_action.signature = signature
    signed_action.signer = signer
    mock_recover_hash.return_value = signer if signature == "0xValidSignature" else "0xOtherSigner"

    if expected_exception:
        with pytest.raises(expected_exception) as e:
            signed_action.validate_signature()
        assert "Invalid signature. Recovered signer does not match expected signer." in str(e.value)
    else:
        signed_action.validate_signature()


@pytest.mark.parametrize(
    "domain_separator, expected_exception",
    [
        ("0x42", None),  # Happy path
        ("0xInvalidHex", ValueError),  # Invalid hex string
        (
            "0x42424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424242424243",  # noqa: mock
            ValueError,
        ),  # Invalid hex string length
    ],
    ids=["happy_path", "invalid_hex", "invalid_length"],
)
def test_domain_separator_property(signed_action, domain_separator, expected_exception):
    signed_action.DOMAIN_SEPARATOR = domain_separator

    if expected_exception:
        with pytest.raises(expected_exception):
            signed_action.domain_separator
    else:
        assert signed_action.domain_separator == bytes.fromhex(domain_separator[2:])


@pytest.mark.parametrize(
    "action_typehash, expected_exception",
    [
        ("0x43", None),  # Happy path
        ("0xInvalidHex", ValueError),  # Invalid hex string
    ],
    ids=["happy_path", "invalid_hex"],
)
def test_action_typehash_property(signed_action, action_typehash, expected_exception):
    signed_action.ACTION_TYPEHASH = action_typehash

    if expected_exception:
        with pytest.raises(expected_exception):
            signed_action.action_typehash
    else:
        assert signed_action.action_typehash == bytes.fromhex(action_typehash[2:])
