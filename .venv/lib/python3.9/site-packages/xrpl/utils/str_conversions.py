"""Various useful string conversions utilities for XRPL."""


def str_to_hex(input: str) -> str:
    """
    Convert a UTF-8-encoded string into hexadecimal encoding.
    XRPL uses hex strings as inputs in fields like `domain`
    in the `AccountSet` transaction.

    Args:
        input: UTF-8-encoded string to convert

    Returns:
        Input encoded as a hex string.
    """
    return input.encode("utf-8").hex()


def hex_to_str(input: str) -> str:
    """
    Convert a hex string into a human-readable string.
    XRPL uses hex strings as inputs in fields like `domain`
    in the `AccountSet` transaction.

    Args:
        input: hex-encoded string to convert

    Returns:
        Input encoded as a human-readable string.
    """
    return bytes.fromhex(input).decode()
