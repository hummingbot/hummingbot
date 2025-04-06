import os
from typing import (
    Any,
    Optional,
    cast,
)

from eth_keyfile.keyfile import (
    KDFType,
)
from eth_utils import (
    is_binary_address,
    is_checksum_address,
    is_dict,
    is_hexstr,
)
from eth_utils.curried import (
    apply_one_of_formatters,
    hexstr_if_str,
    is_0x_prefixed,
    is_address,
    is_bytes,
    is_integer,
    is_list_like,
    is_string,
    to_bytes,
    to_int,
)
from eth_utils.toolz import (
    curry,
    identity,
)
from hexbytes import (
    HexBytes,
)

VALID_EMPTY_ADDRESSES = {None, b"", ""}


def is_none(val: Any) -> bool:
    return val is None


def is_valid_address(value: Any) -> bool:
    return is_binary_address(value) or is_checksum_address(value)


def is_int_or_prefixed_hexstr(val: Any) -> bool:
    if is_integer(val):
        return True
    elif isinstance(val, str) and is_0x_prefixed(val):
        return True
    else:
        return False


def is_empty_or_checksum_address(val: Any) -> bool:
    if val in VALID_EMPTY_ADDRESSES:
        return True
    else:
        return is_valid_address(val)


def is_rpc_structured_access_list(val: Any) -> bool:
    """Returns true if 'val' is a valid JSON-RPC structured access list."""
    if not is_list_like(val):
        return False
    for d in val:
        if not is_dict(d):
            return False
        if len(d) != 2:
            return False
        address = d.get("address")
        storage_keys = d.get("storageKeys")
        if any(_ is None for _ in (address, storage_keys)):
            return False
        if not is_address(address):
            return False
        if not is_list_like(storage_keys):
            return False
        for storage_key in storage_keys:
            if not is_int_or_prefixed_hexstr(storage_key):
                return False
    return True


def is_rlp_structured_access_list(val: Any) -> bool:
    """Returns true if 'val' is a valid rlp-structured access list."""
    if not is_list_like(val):
        return False
    for item in val:
        if not is_list_like(item):
            return False
        if len(item) != 2:
            return False
        address, storage_keys = item
        if not is_address(address):
            return False
        for storage_key in storage_keys:
            if not is_int_or_prefixed_hexstr(storage_key):
                return False
    return True


def is_rpc_structured_authorization_list(val: Any) -> bool:
    """Returns true if 'val' is a valid JSON-RPC structured access list."""
    if not is_list_like(val):
        return False
    if len(val) == 0:
        return False
    for d in val:
        if not is_dict(d):
            return False
        if len(d) != 6:
            return False
        chain_id = d.get("chainId")
        address = d.get("address")
        nonce = d.get("nonce")
        y_parity = d.get("yParity")
        signer_r = d.get("r")
        signer_s = d.get("s")
        if chain_id is None:
            return False
        if not is_int_or_prefixed_hexstr(chain_id):
            return False
        if nonce is None:
            return False
        if not is_int_or_prefixed_hexstr(nonce):
            return False
        if not is_address(address):
            return False
        if y_parity is None:
            return False
        if y_parity not in (0, 1, "0x0", "0x1"):
            return False
        if signer_r is None:
            return False
        if not is_int_or_prefixed_hexstr(signer_r):
            return False
        if signer_s is None:
            return False
        if not is_int_or_prefixed_hexstr(signer_s):
            return False
    return True


def is_rlp_structured_authorization_list(val: Any) -> bool:
    """Returns true if 'val' is a valid rlp-structured access list."""
    if not is_list_like(val):
        return False
    for item in val:
        if not is_list_like(item):
            return False
        if len(item) != 6:
            return False
        chain_id, address, nonce, y_parity, signer_r, signer_s = item
        if chain_id is None:
            return False
        if not is_int_or_prefixed_hexstr(chain_id):
            return False
        if nonce is None:
            return False
        if not is_int_or_prefixed_hexstr(nonce):
            return False
        if not is_address(address):
            return False
        if y_parity is None:
            return False
        if y_parity not in ("0x0", "0x1", 0, 1):
            return False
        if signer_r is None:
            return False
        if not is_int_or_prefixed_hexstr(signer_r):
            return False
        if signer_s is None:
            return False
        if not is_int_or_prefixed_hexstr(signer_s):
            return False
    return True


# type ignored because curry doesn't preserve typing
@curry  # type: ignore[misc]
def is_sequence_of_bytes_or_hexstr(
    value: Any, item_bytes_size: Optional[int] = None, can_be_empty: bool = False
) -> bool:
    if not is_list_like(value):
        return False

    if not can_be_empty and len(value) == 0:
        return False

    if not all(is_bytes(item) or is_hexstr(item) for item in value):
        return False

    if item_bytes_size is not None and not all(
        len(HexBytes(item)) == item_bytes_size for item in value
    ):
        return False

    return True


LEGACY_TRANSACTION_FORMATTERS = {
    "nonce": hexstr_if_str(to_int),
    "gasPrice": hexstr_if_str(to_int),
    "gas": hexstr_if_str(to_int),
    "to": apply_one_of_formatters(
        (
            (is_string, hexstr_if_str(to_bytes)),
            (is_bytes, identity),
            (is_none, lambda val: b""),
        )
    ),
    "value": hexstr_if_str(to_int),
    "data": hexstr_if_str(to_bytes),
    "v": hexstr_if_str(to_int),
    "r": hexstr_if_str(to_int),
    "s": hexstr_if_str(to_int),
}

LEGACY_TRANSACTION_VALID_VALUES = {
    "nonce": is_int_or_prefixed_hexstr,
    "gasPrice": is_int_or_prefixed_hexstr,
    "gas": is_int_or_prefixed_hexstr,
    "to": is_empty_or_checksum_address,
    "value": is_int_or_prefixed_hexstr,
    "data": lambda val: isinstance(val, (int, str, bytes, bytearray)),
    "chainId": lambda val: val is None or is_int_or_prefixed_hexstr(val),
}


def validate_and_set_default_kdf() -> KDFType:
    os_kdf = os.getenv("ETH_ACCOUNT_KDF", "scrypt")
    if os_kdf not in ("pbkdf2", "scrypt"):
        raise ValueError(
            f"Invalid KDF type: {os_kdf}. Must be one of 'pbkdf2' or 'scrypt'"
        )
    return cast(KDFType, os_kdf)
