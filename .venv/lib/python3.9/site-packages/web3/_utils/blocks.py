from typing import (
    Any,
    Optional,
)

from eth_utils import (
    is_bytes,
    is_hex,
    is_integer,
    is_string,
    is_text,
    remove_0x_prefix,
)
from eth_utils.toolz import (
    curry,
)

from web3.exceptions import (
    Web3TypeError,
    Web3ValueError,
)
from web3.types import (
    RPCEndpoint,
)


def is_predefined_block_number(value: Any) -> bool:
    if is_text(value):
        value_text = value
    elif is_bytes(value):
        # `value` could either be random bytes or the utf-8 encoding of
        # one of the words in: {"latest", "pending", "earliest", "safe", "finalized"}
        # We cannot decode the bytes as utf8, because random bytes likely won't be
        # valid. So we speculatively decode as 'latin-1', which cannot fail.
        value_text = value.decode("latin-1")
    elif is_integer(value):
        return False
    else:
        raise Web3TypeError(f"unrecognized block reference: {value!r}")

    return value_text in {"latest", "pending", "earliest", "safe", "finalized"}


def is_hex_encoded_block_hash(value: Any) -> bool:
    if not is_string(value):
        return False
    return len(remove_0x_prefix(value)) == 64 and is_hex(value)


def is_hex_encoded_block_number(value: Any) -> bool:
    if not is_string(value):
        return False
    elif is_hex_encoded_block_hash(value):
        return False
    try:
        value_as_int = int(value, 16)
    except ValueError:
        return False
    return 0 <= value_as_int < 2**256


@curry
def select_method_for_block_identifier(
    value: Any, if_hash: RPCEndpoint, if_number: RPCEndpoint, if_predefined: RPCEndpoint
) -> Optional[RPCEndpoint]:
    if is_predefined_block_number(value):
        return if_predefined
    elif isinstance(value, bytes):
        return if_hash
    elif is_hex_encoded_block_hash(value):
        return if_hash
    elif is_integer(value) and (0 <= value < 2**256):
        return if_number
    elif is_hex_encoded_block_number(value):
        return if_number
    else:
        raise Web3ValueError(
            f"Value did not match any of the recognized block identifiers: {value}"
        )
