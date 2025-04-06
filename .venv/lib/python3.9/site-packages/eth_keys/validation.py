from typing import (
    Any,
)

from eth_utils import (
    ValidationError,
    encode_hex,
    is_bytes,
    is_integer,
)
from eth_utils.toolz import (
    curry,
)

from eth_keys.constants import (
    SECPK1_N,
)


def validate_integer(value: Any) -> None:
    if not is_integer(value) or isinstance(value, bool):
        raise ValidationError(f"Value must be a an integer.  Got: {type(value)}")


def validate_bytes(value: Any) -> None:
    if not is_bytes(value):
        raise ValidationError(f"Value must be a byte string.  Got: {type(value)}")


@curry
def validate_gte(value: Any, minimum: int) -> None:
    validate_integer(value)
    if value < minimum:
        raise ValidationError(
            f"Value {value} is not greater than or equal to {minimum}"
        )


@curry
def validate_lte(value: Any, maximum: int) -> None:
    validate_integer(value)
    if value > maximum:
        raise ValidationError(f"Value {value} is not less than or equal to {maximum}")


validate_lt_secpk1n = validate_lte(maximum=SECPK1_N - 1)


def validate_bytes_length(value: bytes, expected_length: int, name: str) -> None:
    actual_length = len(value)
    if actual_length != expected_length:
        raise ValidationError(
            f"Unexpected {name} length: Expected {expected_length}, but got "
            f"{actual_length} bytes"
        )


def validate_message_hash(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 32, "message hash")


def validate_uncompressed_public_key_bytes(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 64, "uncompressed public key")


def validate_compressed_public_key_bytes(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 33, "compressed public key")
    first_byte = value[0:1]
    if first_byte not in (b"\x02", b"\x03"):
        raise ValidationError(
            "Unexpected compressed public key format: Must start with 0x02 or 0x03, "
            f"but starts with {encode_hex(first_byte)}"
        )


def validate_private_key_bytes(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 32, "private key")


def validate_recoverable_signature_bytes(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 65, "recoverable signature")


def validate_non_recoverable_signature_bytes(value: Any) -> None:
    validate_bytes(value)
    validate_bytes_length(value, 64, "non recoverable signature")


def validate_signature_v(value: int) -> None:
    validate_integer(value)
    validate_gte(value, minimum=0)
    validate_lte(value, maximum=1)


def validate_signature_r_or_s(value: int) -> None:
    validate_integer(value)
    validate_gte(value, 0)
    validate_lt_secpk1n(value)
