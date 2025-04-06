from eth_keys.constants import (
    SECPK1_N,
)


def int_to_byte(value: int) -> bytes:
    return bytes([value])


def coerce_low_s(value: int) -> int:
    """
    Coerce the s component of an ECDSA signature into its low-s form.

    See https://bitcoin.stackexchange.com/questions/83408/in-ecdsa-why-is-r-%E2%88%92s-mod-n-complementary-to-r-s  # noqa: E501
    or https://github.com/ethereum/EIPs/blob/master/EIPS/eip-2.md.
    """  # blocklint:  pragma
    return min(value, -value % SECPK1_N)
