"""Functions for encoding and decoding XRP Ledger addresses and seeds."""

from xrpl.core.addresscodec.codec import (
    SEED_LENGTH,
    decode_account_public_key,
    decode_classic_address,
    decode_node_public_key,
    decode_seed,
    encode_account_public_key,
    encode_classic_address,
    encode_node_public_key,
    encode_seed,
    is_valid_classic_address,
)
from xrpl.core.addresscodec.exceptions import XRPLAddressCodecException
from xrpl.core.addresscodec.main import (
    classic_address_to_xaddress,
    ensure_classic_address,
    is_valid_xaddress,
    xaddress_to_classic_address,
)
from xrpl.core.addresscodec.utils import XRPL_ALPHABET

__all__ = [
    "classic_address_to_xaddress",
    "decode_account_public_key",
    "decode_classic_address",
    "decode_node_public_key",
    "decode_seed",
    "encode_seed",
    "encode_account_public_key",
    "encode_classic_address",
    "encode_node_public_key",
    "ensure_classic_address",
    "is_valid_classic_address",
    "is_valid_xaddress",
    "SEED_LENGTH",
    "xaddress_to_classic_address",
    "XRPLAddressCodecException",
    "XRPL_ALPHABET",
]
