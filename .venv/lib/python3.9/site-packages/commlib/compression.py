import zlib


class CompressionType:
    """CompressionType.

    - NO_COMPRESSION
    - BEST_SPEED
    - BEST_COMPRESSION
    - DEFAULT_COMPRESSION
    """

    NO_COMPRESSION = 0
    BEST_SPEED = zlib.Z_BEST_SPEED
    BEST_COMPRESSION = zlib.Z_BEST_COMPRESSION
    DEFAULT_COMPRESSION = zlib.Z_DEFAULT_COMPRESSION


def inflate_str(text: str,
                compression_type: int = CompressionType.DEFAULT_COMPRESSION):
    """inflate_str.

    Args:
        text (str): text
        compression_type (int): compression_type
    """
    return zlib.compress(text.encode(), compression_type)


def deflate(data: bytes):
    """deflate.

    Args:
        data (bytes): data
    """
    return zlib.decompress(data)
