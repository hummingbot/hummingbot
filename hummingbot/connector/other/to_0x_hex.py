from hexbytes import HexBytes


def to_0x_hex(signature: HexBytes) -> str:
    """
    Convert a string to a 0x-prefixed hex string.
    """
    if hasattr(signature, "to_0x_hex"):
        return signature.to_0x_hex()

    return hex if (hex := signature.hex()).startswith("0x") else f"0x{hex}"
