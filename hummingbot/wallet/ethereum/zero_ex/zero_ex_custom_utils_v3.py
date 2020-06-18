from copy import copy
from enum import auto, Enum
from eth_typing import HexStr
from eth_utils import keccak, remove_0x_prefix, to_bytes, to_checksum_address
from mypy_extensions import TypedDict
from typing import (
    cast,
    Tuple,
    Union
)
from zero_ex.order_utils import (
    _convert_ec_signature_to_vrs_hex,
    _parse_signature_hex_as_vrs,
    _parse_signature_hex_as_rsv
)
from zero_ex.dev_utils.type_assertions import (
    assert_is_address,
    assert_is_hex_string,
    assert_is_provider,
)
from zero_ex.contract_addresses import chain_to_addresses, ChainId
from zero_ex.contract_wrappers.exchange import Exchange
from web3.providers.base import BaseProvider


class Order(TypedDict):
    makerAddress: str
    takerAddress: str
    feeRecipientAddress: str
    senderAddress: str
    makerAssetAmount: int
    takerAssetAmount: int
    makerFee: int
    takerFee: int
    expirationTimeSeconds: int
    salt: int
    makerAssetData: bytes
    takerAssetData: bytes
    makerFeeAssetData: bytes
    takerFeeAssetData: bytes


class _Constants:
    """Static data used by order utilities."""

    null_address = "0x0000000000000000000000000000000000000000"

    eip191_header = b"\x19\x01"

    eip712_domain_separator_schema_hash = keccak(
        b"EIP712Domain("
        + b"string name,"
        + b"string version,"
        + b"uint256 chainId,"
        + b"address verifyingContract"
        + b")"
    )

    eip712_domain_struct_header = (
        eip712_domain_separator_schema_hash
        + keccak(b"0x Protocol")
        + keccak(b"3.0.0")
    )

    eip712_order_schema_hash = keccak(
        b"Order("
        + b"address makerAddress,"
        + b"address takerAddress,"
        + b"address feeRecipientAddress,"
        + b"address senderAddress,"
        + b"uint256 makerAssetAmount,"
        + b"uint256 takerAssetAmount,"
        + b"uint256 makerFee,"
        + b"uint256 takerFee,"
        + b"uint256 expirationTimeSeconds,"
        + b"uint256 salt,"
        + b"bytes makerAssetData,"
        + b"bytes takerAssetData,"
        + b"bytes makerFeeAssetData,"
        + b"bytes takerFeeAssetData"
        + b")"
    )

    class SignatureType(Enum):
        """Enumeration of known signature types."""

        ILLEGAL = 0
        INVALID = auto()
        EIP712 = auto()
        ETH_SIGN = auto()
        WALLET = auto()
        VALIDATOR = auto()
        PRE_SIGNED = auto()
        N_SIGNATURE_TYPES = auto()


def generate_order_hash_hex(
    order: Order, exchange_address: str, chain_id: int
) -> str:
    """Calculate the hash of the given order as a hexadecimal string.
    :param order: The order to be hashed.  Must conform to `the 0x order JSON schema <https://github.com/0xProject/0x-monorepo/blob/development/packages/json-schemas/schemas/order_schema.json>`_.
    :param exchange_address: The address to which the 0x Exchange smart
        contract has been deployed.
    :returns: A string, of ASCII hex digits, representing the order hash.
    Inputs and expected result below were copied from
    @0x/order-utils/test/order_hash_test.ts
    >>> generate_order_hash_hex(
    ...     Order(
    ...         makerAddress="0x0000000000000000000000000000000000000000",
    ...         takerAddress="0x0000000000000000000000000000000000000000",
    ...         feeRecipientAddress="0x0000000000000000000000000000000000000000",
    ...         senderAddress="0x0000000000000000000000000000000000000000",
    ...         makerAssetAmount="0",
    ...         takerAssetAmount="0",
    ...         makerFee="0",
    ...         takerFee="0",
    ...         expirationTimeSeconds="0",
    ...         salt="0",
    ...         makerAssetData=((0).to_bytes(1, byteorder='big') * 20),
    ...         takerAssetData=((0).to_bytes(1, byteorder='big') * 20),
    ...         makerFeeAssetData=((0).to_bytes(1, byteorder='big') * 20),
    ...         takerFeeAssetData=((0).to_bytes(1, byteorder='big') * 20),
    ...     ),
    ...     exchange_address="0x1dc4c1cefef38a777b15aa20260a54e584b16c48",
    ...     chain_id=1337
    ... )
    'cb36e4fedb36508fb707e2c05e21bffc7a72766ccae93f8ff096693fff7f1714'
    """  # noqa: E501 (line too long)

    def pad_20_bytes_to_32(twenty_bytes: bytes):
        return bytes(12) + twenty_bytes

    def int_to_32_big_endian_bytes(i: int):
        return i.to_bytes(32, byteorder="big")

    eip712_domain_struct_hash = keccak(
        _Constants.eip712_domain_struct_header
        + int_to_32_big_endian_bytes(int(chain_id))
        + pad_20_bytes_to_32(to_bytes(hexstr=exchange_address))
    )

    def ensure_bytes(str_or_bytes: Union[str, bytes]) -> bytes:
        return (
            to_bytes(hexstr=cast(bytes, str_or_bytes))
            if isinstance(str_or_bytes, str)
            else str_or_bytes
        )

    eip712_order_struct_hash = keccak(
        _Constants.eip712_order_schema_hash
        + pad_20_bytes_to_32(to_bytes(hexstr=order["makerAddress"]))
        + pad_20_bytes_to_32(to_bytes(hexstr=order["takerAddress"]))
        + pad_20_bytes_to_32(to_bytes(hexstr=order["feeRecipientAddress"]))
        + pad_20_bytes_to_32(to_bytes(hexstr=order["senderAddress"]))
        + int_to_32_big_endian_bytes(int(order["makerAssetAmount"]))
        + int_to_32_big_endian_bytes(int(order["takerAssetAmount"]))
        + int_to_32_big_endian_bytes(int(order["makerFee"]))
        + int_to_32_big_endian_bytes(int(order["takerFee"]))
        + int_to_32_big_endian_bytes(int(order["expirationTimeSeconds"]))
        + int_to_32_big_endian_bytes(int(order["salt"]))
        + keccak(ensure_bytes(order["makerAssetData"]))
        + keccak(ensure_bytes(order["takerAssetData"]))
        + keccak(ensure_bytes(order["makerFeeAssetData"]))
        + keccak(ensure_bytes(order["takerFeeAssetData"]))
    )

    return keccak(
        _Constants.eip191_header
        + eip712_domain_struct_hash
        + eip712_order_struct_hash
    ).hex()


def is_valid_signature(
    provider: BaseProvider, data: str, signature: str, signer_address: str, chain_id: int = 1
) -> bool:
    """Check the validity of the supplied signature.
    Check if the supplied `signature`:code: corresponds to signing `data`:code:
    with the private key corresponding to `signer_address`:code:.
    :param provider: A Web3 provider able to access the 0x Exchange contract.
    :param data: The hex encoded data signed by the supplied signature.
    :param signature: The hex encoded signature.
    :param signer_address: The hex encoded address that signed the data to
        produce the supplied signature.
    :returns: Tuple consisting of a boolean and a string.  Boolean is true if
        valid, false otherwise.  If false, the string describes the reason.
    >>> is_valid_signature(
    ...     Web3.HTTPProvider("http://127.0.0.1:8545"),
    ...     '0x6927e990021d23b1eb7b8789f6a6feaf98fe104bb0cf8259421b79f9a34222b0',
    ...     '0x1B61a3ed31b43c8780e905a260a35faefcc527be7516aa11c0256729b5b351bc3340349190569279751135161d22529dc25add4f6069af05be04cacbda2ace225403',
    ...     '0x5409ed021d9299bf6814279a6a1411a7e866a631',
    ... )
    True
    """  # noqa: E501 (line too long)
    assert_is_provider(provider, "provider")
    assert_is_hex_string(data, "data")
    assert_is_hex_string(signature, "signature")
    assert_is_address(signer_address, "signer_address")

    return Exchange(
        provider,
        chain_to_addresses(
            ChainId(
                chain_id  # defaults to always be mainnet
            )
        ).exchange,
    ).is_valid_hash_signature.call(
        bytes.fromhex(remove_0x_prefix(HexStr(data))),
        to_checksum_address(signer_address),
        bytes.fromhex(remove_0x_prefix(HexStr(signature))),
    )


def jsdict_order_to_struct(jsdict: dict) -> Order:
    order = cast(Order, copy(jsdict))

    order["makerAssetData"] = bytes.fromhex(
        remove_0x_prefix(jsdict["makerAssetData"])
    )
    order["takerAssetData"] = bytes.fromhex(
        remove_0x_prefix(jsdict["takerAssetData"])
    )
    order["makerFeeAssetData"] = bytes.fromhex(
        remove_0x_prefix(jsdict["makerFeeAssetData"])
    )
    order["takerFeeAssetData"] = bytes.fromhex(
        remove_0x_prefix(jsdict["takerFeeAssetData"])
    )

    del order["chainId"]
    del order["exchangeAddress"]

    return order


def convert_order_to_tuple(order: Order) -> Tuple[str, any]:
    order_tuple = (to_checksum_address(order["makerAddress"]),
                   to_checksum_address(order["takerAddress"]),
                   to_checksum_address(order["feeRecipientAddress"]),
                   to_checksum_address(order["senderAddress"]),
                   int(order["makerAssetAmount"]),
                   int(order["takerAssetAmount"]),
                   int(order["makerFee"]),
                   int(order["takerFee"]),
                   int(order["expirationTimeSeconds"]),
                   int(order["salt"]),
                   order["makerAssetData"],
                   order["takerAssetData"],
                   order["makerFeeAssetData"],
                   order["takerFeeAssetData"])
    return order_tuple


# fix_signature extracts the logic used for formatting the signature required by the 0x protocol from 0x's custom
# sign_hash helper.
# https://github.com/0xProject/0x-monorepo/blob/development/python-packages/order_utils/src/zero_ex/order_utils/__init__.py#L462
def fix_signature(provider, signer_address, hash_hex, signature, chain_id = 1) -> str:
    valid_v_param_values = [27, 28]

    # HACK: There is no consensus on whether the signatureHex string should be
    # formatted as v + r + s OR r + s + v, and different clients (even
    # different versions of the same client) return the signature params in
    # different orders. In order to support all client implementations, we
    # parse the signature in both ways, and evaluate if either one is a valid
    # signature.  r + s + v is the most prevalent format from eth_sign, so we
    # attempt this first.

    ec_signature = _parse_signature_hex_as_rsv(signature)
    if ec_signature["v"] in valid_v_param_values:
        signature_as_vrst_hex = (
            _convert_ec_signature_to_vrs_hex(ec_signature)
            + _Constants.SignatureType.ETH_SIGN.value.to_bytes(
                1, byteorder="big"
            ).hex()
        )

        valid = is_valid_signature(
            provider, hash_hex, signature_as_vrst_hex, signer_address, chain_id
        )

        if valid is True:
            return signature_as_vrst_hex

    ec_signature = _parse_signature_hex_as_vrs(signature)
    if ec_signature["v"] in valid_v_param_values:
        signature_as_vrst_hex = (
            _convert_ec_signature_to_vrs_hex(ec_signature)
            + _Constants.SignatureType.ETH_SIGN.value.to_bytes(
                1, byteorder="big"
            ).hex()
        )

        valid = is_valid_signature(
            provider, hash_hex, signature_as_vrst_hex, signer_address, chain_id
        )

        if valid is True:
            return signature_as_vrst_hex

    raise RuntimeError(
        "Signature returned from web3 provider is in an unknown format."
        + " Attempted to parse as RSV and as VRS."
    )
