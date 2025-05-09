from decimal import Decimal

import pytest
from eth_abi.abi import decode
from eth_account import Account
from hexbytes import HexBytes
from web3 import Web3

from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_web_utils import decimal_to_big_int
from hummingbot.connector.other.derive_common_utils import SignedAction, TradeModuleData


@pytest.fixture
def trade_module_data():
    return TradeModuleData(
        asset_address=Web3.to_checksum_address("0x742d35Cc6634C0532925a3b844Bc454e4438f44e"),  # noqa: mock
        sub_id=1,
        limit_price=Decimal("100.5"),
        amount=Decimal("10"),
        max_fee=Decimal("0.1"),
        recipient_id=12345,
        is_bid=True,
    )


@pytest.fixture
def signed_action(trade_module_data):
    return SignedAction(
        subaccount_id=1,
        owner=Web3.to_checksum_address("0x3F5CE5FBFe3E9af3971dD833D26BA9b5C936F0bE"),  # noqa: mock
        signer=Web3().eth.account.from_key("0x4c0883a69102937d6231471b5dbb6204fe512961708279ca6f297d6b50ab8148").address,  # noqa: mock
        signature_expiry_sec=1700000000,
        nonce=1695836058725001,
        module_address=Web3.to_checksum_address("0x53d284357ec70cE289D6D64134DfAc8E511c8a3D"),  # noqa: mock
        DOMAIN_SEPARATOR="0x0000000000000000000000000000000000000000000000000000000000000000",  # noqa: mock
        ACTION_TYPEHASH="0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17",  # noqa: mock
        module_data=trade_module_data,
    )


def test_trade_module_encoding(trade_module_data):
    encoded_data = trade_module_data.to_abi_encoded()
    decoded_data = decode(
        [
            "address",
            "uint256",
            "int256",
            "int256",
            "uint256",
            "uint256",
            "bool"
        ],
        encoded_data
    )

    assert Web3.to_checksum_address(decoded_data[
        0
    ]) == trade_module_data.asset_address
    assert decoded_data[
        1
    ] == trade_module_data.sub_id
    assert decoded_data[
        2
    ] == decimal_to_big_int(trade_module_data.limit_price)
    assert decoded_data[
        3
    ] == decimal_to_big_int(trade_module_data.amount)
    assert decoded_data[
        4
    ] == decimal_to_big_int(trade_module_data.max_fee)
    assert decoded_data[
        5
    ] == trade_module_data.recipient_id
    assert decoded_data[
        6
    ] == trade_module_data.is_bid


def test_trade_module_json(trade_module_data):
    json_data = trade_module_data.to_json()
    assert json_data == {
        "limit_price": "100.5",
        "amount": "10",
        "max_fee": "0.1",
    }


def test_signed_action_to_json(signed_action):
    json_data = signed_action.to_json()
    assert json_data[
        "subaccount_id"
    ] == signed_action.subaccount_id
    assert json_data[
        "nonce"
    ] == signed_action.nonce
    assert json_data[
        "signer"
    ] == signed_action.signer
    assert json_data[
        "signature_expiry_sec"
    ] == signed_action.signature_expiry_sec


def test_signed_action_sign_and_validate(signed_action):
    private_key = "0x4c0883a69102937d6231471b5dbb6204fe512961708279ca6f297d6b50ab8148"  # noqa: mock

    # Generate signature
    signature = signed_action.sign(private_key)

    # Convert signature to hex if it's in bytes
    if isinstance(signature, bytes):
        signature = signature.hex()

    if not signature.startswith("0x"):
        signature = f"0x{signature}"

    # Assertions
    assert isinstance(signature, str)
    assert signature.startswith("0x"), f"Signature format is incorrect: {signature}"

    # Attach signature to the object
    signed_action.signature = signature

    # Compute hash and recover the signer
    data_hash = signed_action._to_typed_data_hash()
    recovered_signer = Account._recover_hash(data_hash, signature=HexBytes(signature))

    # Debugging: Print hashes & addresses
    print(f"Data hash: {data_hash.hex()}")
    print(f"Expected signer: {signed_action.signer.lower()}")
    print(f"Recovered signer: {recovered_signer.lower()}")

    # Validate signature
    assert recovered_signer.lower() == signed_action.signer.lower()

    # Run validate_signature() to ensure it works
    signed_action.validate_signature()
