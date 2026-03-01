"""
EIP-712 order signing utilities for the GRVT perpetual connector.

GRVT uses EIP-712 typed-data signing to authenticate order placement.
The signer's Ethereum private key is used to produce an ECDSA signature over a
structured order message that the GRVT smart-contract verifies on-chain.

Domain:
    name:    "GRVT Exchange"
    version: "0"
    chainId: 325  (mainnet) / 326 (testnet)

Primary type: Order
    subAccountID   uint64
    isMarket       bool
    timeInForce    uint8  (1=GTC, 3=IOC, 4=FOK)
    postOnly       bool
    reduceOnly     bool
    legs           OrderLeg[]
    nonce          uint32
    expiration     int64   (nanoseconds since epoch)

OrderLeg:
    assetID          uint256   (instrument_hash from API)
    contractSize     uint64    (size * 10^base_decimals)
    limitPrice       uint64    (price * 1e9)
    isBuyingContract bool
"""
import random
import time
from decimal import Decimal
from typing import Any, Dict

from eth_account import Account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS

_EIP712_ORDER_TYPES = {
    "Order": [
        {"name": "subAccountID", "type": "uint64"},
        {"name": "isMarket", "type": "bool"},
        {"name": "timeInForce", "type": "uint8"},
        {"name": "postOnly", "type": "bool"},
        {"name": "reduceOnly", "type": "bool"},
        {"name": "legs", "type": "OrderLeg[]"},
        {"name": "nonce", "type": "uint32"},
        {"name": "expiration", "type": "int64"},
    ],
    "OrderLeg": [
        {"name": "assetID", "type": "uint256"},
        {"name": "contractSize", "type": "uint64"},
        {"name": "limitPrice", "type": "uint64"},
        {"name": "isBuyingContract", "type": "bool"},
    ],
}

_TIME_IN_FORCE_TO_INT = {
    CONSTANTS.TIME_IN_FORCE_GTC: 1,
    CONSTANTS.TIME_IN_FORCE_IOC: 3,
    CONSTANTS.TIME_IN_FORCE_FOK: 4,
}

_CHAIN_IDS = {
    CONSTANTS.DOMAIN: 325,
    CONSTANTS.TESTNET_DOMAIN: 326,
}

# GRVT price units: multiply USD price by 1e9 to get uint64
_PRICE_MULTIPLIER = Decimal("1000000000")
# Nanoseconds per second
_NSEC_IN_SEC = 1_000_000_000
# Order valid for 24 h by default
_DEFAULT_EXPIRY_NS = 24 * 60 * 60 * _NSEC_IN_SEC


def _to_uint(value: Any) -> int:
    """Parse an integer from a string, int, or hex string."""
    if isinstance(value, int):
        return value
    value_str = str(value).strip()
    if value_str.lower().startswith("0x"):
        return int(value_str, 16)
    return int(value_str)


def _domain_data(domain: str) -> Dict[str, Any]:
    return {
        "name": "GRVT Exchange",
        "version": "0",
        "chainId": _CHAIN_IDS.get(domain, _CHAIN_IDS[CONSTANTS.DOMAIN]),
    }


def _to_hex_32(value: int) -> str:
    """Encode an integer as a 0x-prefixed 32-byte big-endian hex string."""
    return f"0x{value.to_bytes(32, byteorder='big').hex()}"


def build_order_signature(
    private_key: str,
    domain: str,
    sub_account_id: str,
    instrument_hash: Any,
    base_decimals: Any,
    is_market: bool,
    time_in_force: str,
    post_only: bool,
    reduce_only: bool,
    is_buying_contract: bool,
    size: Decimal,
    limit_price: Decimal,
) -> Dict[str, Any]:
    """
    Build and return an EIP-712 order signature dict for the GRVT REST API.

    The returned dict contains the fields expected by the GRVT ``create_order``
    endpoint inside the ``order.signature`` field:
        r, s, v       - ECDSA signature components
        expiration    - nanosecond expiry timestamp (as string)
        nonce         - random 32-bit nonce (int)
        signer        - checksummed Ethereum address of the signing key

    :param private_key:        Ethereum private key (hex string, with or without 0x prefix).
    :param domain:             Connector domain constant (``CONSTANTS.DOMAIN`` or ``TESTNET_DOMAIN``).
    :param sub_account_id:     GRVT sub-account ID (string or int).
    :param instrument_hash:    Instrument hash from GRVT's instrument API (hex string or int).
    :param base_decimals:      Decimal precision of the base asset (int or string).
    :param is_market:          True for market orders.
    :param time_in_force:      One of TIME_IN_FORCE_GTC / IOC / FOK constant strings.
    :param post_only:          True to mark as post-only (LIMIT_MAKER).
    :param reduce_only:        True to mark as reduce-only (close position).
    :param is_buying_contract: True for BUY, False for SELL.
    :param size:               Order quantity in base asset units.
    :param limit_price:        Limit price in quote (USD) units; pass Decimal("0") for market.
    :returns: Signature dict ready to embed in the order payload.
    :raises ValueError: If instrument_hash / base_decimals are missing or time_in_force is invalid.
    """
    if instrument_hash is None:
        raise ValueError("Missing instrument_hash in GRVT instrument data for signing.")
    if base_decimals is None:
        raise ValueError("Missing base_decimals in GRVT instrument data for signing.")
    if time_in_force not in _TIME_IN_FORCE_TO_INT:
        raise ValueError(f"Unsupported GRVT time_in_force for signing: {time_in_force!r}")

    sub_account_id_uint = _to_uint(sub_account_id)
    asset_id_uint = _to_uint(instrument_hash)
    base_decimals_int = int(base_decimals)

    nonce = random.randint(0, (2 ** 32) - 1)
    expiration = time.time_ns() + _DEFAULT_EXPIRY_NS

    leg = {
        "assetID": asset_id_uint,
        "contractSize": int(Decimal(size) * (Decimal(10) ** base_decimals_int)),
        "limitPrice": int(Decimal(limit_price) * _PRICE_MULTIPLIER),
        "isBuyingContract": bool(is_buying_contract),
    }

    message_data = {
        "subAccountID": sub_account_id_uint,
        "isMarket": bool(is_market),
        "timeInForce": _TIME_IN_FORCE_TO_INT[time_in_force],
        "postOnly": bool(post_only),
        "reduceOnly": bool(reduce_only),
        "legs": [leg],
        "nonce": nonce,
        "expiration": expiration,
    }

    signable_message = encode_typed_data(
        _domain_data(domain),
        _EIP712_ORDER_TYPES,
        message_data,
    )
    signed_message = Account.sign_message(signable_message, private_key)
    signer = Account.from_key(private_key).address

    return {
        "r": _to_hex_32(signed_message.r),
        "s": _to_hex_32(signed_message.s),
        "v": signed_message.v,
        "expiration": str(expiration),
        "nonce": nonce,
        "signer": signer,
    }
