# Non-recoverable signatures are encoded using a DER sequence of two integers
# We locally implement serialization and deserialization for this specific spec
#   with constrained inputs.
# This is done locally to avoid importing a 3rd-party library, in this very sensitive
# project. asn1tools and pyasn1 were used as reference APIs, see how in
# tests/core/test_utils_asn1.py
#
# See more about DER encodings, and ASN.1 in general, here:
# http://luca.ntop.org/Teaching/Appunti/asn1.html
#
# These methods are NOT intended for external use outside of this project. They do not
# fully validate inputs and make assumptions that are not *generally* true.

from typing import (
    Iterator,
    Tuple,
)

from eth_utils import (
    apply_to_return_value,
    big_endian_to_int,
    int_to_big_endian,
)


@apply_to_return_value(bytes)
def two_int_sequence_encoder(signature_r: int, signature_s: int) -> Iterator[int]:
    """
    Encode two integers using DER, defined as:

    ::

        ECDSASpec DEFINITIONS ::= BEGIN
              ECDSASignature ::= SEQUENCE {
                 r   INTEGER,
                 s   INTEGER
             }
        END

    Only a subset of integers are supported: positive, 32-byte ints.

    See: https://docs.microsoft.com/en-us/windows/desktop/seccertenroll/about-sequence
    """
    # Sequence tag
    yield 0x30

    encoded1 = _encode_int(signature_r)
    encoded2 = _encode_int(signature_s)

    # Sequence length
    yield len(encoded1) + len(encoded2)

    yield from encoded1
    yield from encoded2


def two_int_sequence_decoder(encoded: bytes) -> Tuple[int, int]:
    """
    Decode bytes to two integers using DER, defined as:

    ::

        ECDSASpec DEFINITIONS ::= BEGIN
              ECDSASignature ::= SEQUENCE {
                 r   INTEGER,
                 s   INTEGER
             }
        END

    Only a subset of integers are supported: positive, 32-byte ints.

    r is returned first, and s is returned second

    See: https://docs.microsoft.com/en-us/windows/desktop/seccertenroll/about-sequence
    """
    if encoded[0] != 0x30:
        raise ValueError(
            f"Encoded sequence must start with 0x30 byte, but got {encoded[0]}"
        )

    # skip sequence length
    int1, rest = _decode_int(encoded[2:])
    int2, empty = _decode_int(rest)

    if len(empty) != 0:
        raise ValueError(
            "Encoded sequence must not contain any trailing data, but had "
            f"{repr(empty)}"
        )

    return int1, int2


@apply_to_return_value(bytes)
def _encode_int(primitive: int) -> Iterator[int]:
    # See: https://docs.microsoft.com/en-us/windows/desktop/seccertenroll/about-integer

    # Integer tag
    yield 0x02

    encoded = int_to_big_endian(primitive)
    if encoded[0] >= 128:
        # Indicate that integer is positive
        # (it always is, but doesn't always need the flag)
        yield len(encoded) + 1
        yield 0x00
    else:
        yield len(encoded)

    yield from encoded


def _decode_int(encoded: bytes) -> Tuple[int, bytes]:
    # See: https://docs.microsoft.com/en-us/windows/desktop/seccertenroll/about-integer

    if encoded[0] != 0x02:
        raise ValueError(
            "Encoded value must be an integer, starting with on 0x02 byte, but got "
            f"{encoded[0]}"
        )

    length = encoded[1]
    # to_int can handle leading zeros
    decoded_int = big_endian_to_int(encoded[2 : 2 + length])

    return decoded_int, encoded[2 + length :]
