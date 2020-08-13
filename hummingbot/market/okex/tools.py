import zlib



def inflate(data):
    """decrypts the OKEx data.
    Copied from OKEx SDK: https://github.com/okex/V3-Open-API-SDK/blob/d8becc67af047726c66d9a9b29d99e99c595c4f7/okex-python-sdk-api/websocket_example.py#L46"""
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated