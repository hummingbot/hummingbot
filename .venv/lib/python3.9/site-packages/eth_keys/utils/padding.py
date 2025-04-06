def pad32(value: bytes) -> bytes:
    return value.rjust(32, b"\x00")
